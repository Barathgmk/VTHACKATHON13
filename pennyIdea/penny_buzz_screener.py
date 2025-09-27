# penny_from_subreddit.py
import os, re, datetime as dt
from pathlib import Path
from collections import Counter, defaultdict

import pandas as pd
import yfinance as yf
from tabulate import tabulate
from dotenv import load_dotenv
# sentiment
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# reddit api
import praw

# ---------------- config (edit if you want) ----------------
SUBREDDITS      = ["pennystocks", "stocks", "wallstreetbets"]
LOOKBACK_DAYS   = 3          # scan newest posts/comments from ~last N days
POST_LIMIT_EACH = 400        # per-subreddit cap
PRICE_MAX       = 5.00       # penny threshold
MIN_DOLLAR_VOL  = 200_000    # min 10-day avg dollar volume (price*volume)
# -----------------------------------------------------------
RUN_NOW = dt.datetime.now(dt.timezone.utc)
CUTOFF_TS = RUN_NOW.timestamp() - LOOKBACK_DAYS * 86400
# load .env (simple)
def load_env_strict():
    dotenv_path = Path(__file__).resolve().parent / ".env"
    if not dotenv_path.exists():
        raise FileNotFoundError(f".env not found at: {dotenv_path}")
    # override=True ensures we refresh values every run
    load_dotenv(dotenv_path=dotenv_path, override=True)


def ensure_vader():
    try:
        nltk.data.find("sentiment/vader_lexicon.zip")
    except LookupError:
        nltk.download("vader_lexicon")

COMMON_WORDS = {
    "A","I","THE","DD","YOLO","ALL","ETF","OTC","USA","CPI","GDP",
    "FOR","WITH","THIS","HOLD","GAIN","LOSS","CALL","PUT","CEO",
    "EV","IPO","AI","CPU","GPU","USD", "ADD", "UP"
}
TICKER_RE = re.compile(r"\b[A-Z]{1,5}\b")

def extract_tickers(text: str):
    if not text: return []
    return [t for t in TICKER_RE.findall(text.upper()) if t not in COMMON_WORDS]

def init_reddit():
    load_env_strict()
    cid  = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    csec = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    ua   = os.environ.get("REDDIT_USER_AGENT", "penny-scan/0.1 by u/unknown").strip()

    # debug (masked) so you can confirm it loaded each run
    print(f"Env check -> CID={cid[:4]+'...' if cid else '<missing>'}  "
          f"SECRET={(csec[:4]+'...') if csec else '<missing>'}  UA={ua!r}")

    if not cid or not csec:
        raise RuntimeError("Missing REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env")

    import praw
    return praw.Reddit(client_id=cid, client_secret=csec, user_agent=ua, ratelimit_seconds=5)

def gather_mentions(subreddits, days_back, limit_each) -> pd.DataFrame:
    ensure_vader()
    sia = SentimentIntensityAnalyzer()
    reddit = init_reddit()
    cutoff = dt.datetime.now(dt.timezone.utc).timestamp() - days_back * 86400

    counts = Counter()
    sent_sum = defaultdict(float)

    for sub in subreddits:
        for post in reddit.subreddit(sub).new(limit=limit_each):
            if post.created_utc < cutoff:
                continue
            body = f"{post.title}\n{post.selftext or ''}"
            pticks = set(extract_tickers(body))
            if pticks:
                sc = sia.polarity_scores(body)["compound"]
                for t in pticks:
                    counts[t] += 1
                    sent_sum[t] += sc
            post.comments.replace_more(limit=0)
            comments = list(post.comments.list())
            comments.sort(key=lambda c: (int(getattr(c, "created_utc", 0)), getattr(c, "id", "")))

            for c in comments:
                if c.created_utc < cutoff: 
                    continue
            txt = c.body or ""
            cticks = set(extract_tickers(txt))
            if cticks:
                sc = sia.polarity_scores(txt)["compound"]
            for t in cticks:
                counts[t] += 1
                sent_sum[t] += sc
           
            

    rows = []
    for t, m in counts.most_common():
        s = sent_sum[t] / m if m else 0.0
        rows.append({"ticker": t, "mentions": m, "avg_sentiment": s})
    return pd.DataFrame(rows)

def finance_filter(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: 
        return df
    tickers = df["ticker"].tolist()
    hist = yf.download(tickers=tickers, period="1mo", interval="1d",
                       auto_adjust=True, progress=False, threads=True)

    if isinstance(hist.columns, pd.MultiIndex):
        close = hist["Close"]; vol = hist["Volume"]
    else:
        close = hist["Close"].to_frame(); vol = hist["Volume"].to_frame()

    last   = close.ffill().iloc[-1]
    avg_dv = (close.tail(10) * vol.tail(10)).mean()

    out = df.merge(pd.DataFrame({"ticker": last.index, "last": last.values}),
                   on="ticker", how="left").merge(
         pd.DataFrame({"ticker": avg_dv.index, "avg_dollar_vol": avg_dv.values}),
                   on="ticker", how="left")

    out = out.dropna(subset=["last", "avg_dollar_vol"])
    out = out[~out["ticker"].str.contains(r"[.\-]")]  # basic OTC filter (optional)

    out = out[(out["last"] > 0) & (out["last"] <= PRICE_MAX) &
              (out["avg_dollar_vol"] >= MIN_DOLLAR_VOL)].copy()

    out["rank_score"] = out["mentions"] * (1 + out["avg_sentiment"])
    cols = ["ticker","mentions","avg_sentiment","last","avg_dollar_vol","rank_score"]
    return out.sort_values(["rank_score","mentions","avg_sentiment"], ascending=False)[cols].reset_index(drop=True)

def main():
    print(f"Scanning {', '.join('r/'+s for s in SUBREDDITS)} (~{LOOKBACK_DAYS} days)…")
    raw = gather_mentions(SUBREDDITS, LOOKBACK_DAYS, POST_LIMIT_EACH)
    if raw.empty:
        print("No ticker mentions found in the lookback window.")
        return
    ranked = finance_filter(raw)
    ranked = ranked.sort_values(
    ["rank_score", "mentions", "avg_sentiment", "ticker"],
    ascending=[False, False, False, True]
).reset_index(drop=True)
    if ranked.empty:
        print("No penny candidates after price/liquidity filters. Try lowering MIN_DOLLAR_VOL or extend LOOKBACK_DAYS.")
        print("\nTop raw mentions (unfiltered):")
        print(tabulate(raw.head(20), headers='keys', tablefmt='github'))
        return

    print(tabulate(ranked.head(30), headers="keys", tablefmt="github", floatfmt=".4f"))
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d_%H%M%S")
    ranked.to_csv(f"penny_candidates_{ts}.csv", index=False)
    print(f"\nSaved: penny_candidates_{ts}.csv")

if __name__ == "__main__":
    main()
