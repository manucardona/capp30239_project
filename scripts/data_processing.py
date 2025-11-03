import pandas as pd
import re

import unidecode
import unicodedata
from collections import Counter

import string
import nltk
from nltk.corpus import stopwords

from typing import Optional

# Load analyzer once (Spanish sentiment)
try:
    from pysentimiento import create_analyzer
    _analyzer_es = create_analyzer(task="sentiment", lang="es")
except Exception as e:
    _analyzer_es = None
    print("Could not load pysentimiento analyzer. "
          "Install/verify `pysentimiento`, `transformers`, and `torch`.\n", e)

# Small helpers 
_LABEL_TO_SCORE = {"POS": 1.0, "NEU": 0.0, "NEG": -1.0}
_SPANISH_LABEL = {"POS": "Positive", "NEU": "Neutral", "NEG": "Negative"}

# Download Spanish stopwords (only once)
nltk.download('stopwords')

# Define global Spanish stopword list
SPANISH_STOPWORDS = set(stopwords.words('spanish'))

MEXICO_STATES = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", 
    "Chiapas", "Chihuahua", "Ciudad de Mexico", "Coahuila", "Colima", 
    "Durango", "Estado de Mexico", "Guanajuato", "Guerrero", "Hidalgo", 
    "Jalisco", "Michoacan", "Morelos", "Nayarit", "Nuevo Leon", 
    "Oaxaca", "Puebla", "Queretaro", "Quintana Roo", "San Luis Potosi", 
    "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", 
    "Veracruz", "Yucatan", "Zacatecas"
]

def parse_spanish_date(raw_date):
    """
    Convert a messy Spanish date string (e.g., 
    'jueves, 16 de octubre de 2025Fecha de publicación')
    into a standard datetime.date object.
    Parameters:
        raw_date (str): Raw date string in Spanish.
    Returns:
        pd.Timestamp or pd.NaT: Parsed date or NaT if parsing fails.
    """
    if not isinstance(raw_date, str):
        return pd.NaT

    # 1. Clean unwanted text
    clean = raw_date.lower()
    clean = re.sub(r"fecha.*", "", clean).strip()  # remove "Fecha de publicación" and after
    clean = re.sub(r"[,]", "", clean)  # remove commas

    # 2. Map month names in spanish to numbers
    months = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "setiembre": 9, "octubre": 10,
        "noviembre": 11, "diciembre": 12
    }

    # 3. Extract day, month, year
    pattern = r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})"
    match = re.search(pattern, clean)
    if not match:
        return pd.NaT

    day = int(match.group(1))
    month_str = match.group(2)
    year = int(match.group(3))

    # 4. Normalize month
    month = months.get(month_str, None)
    if not month:
        return pd.NaT

    # 5. Return datetime
    try:
        return pd.Timestamp(year=year, month=month, day=day).date()
    except Exception:
        return pd.NaT
    
def flatten_data(data):
    """
    Flatten nested JSON data into a pandas DataFrame.
    Forward fill missing speaker names.
    Parameters:
        data (list): List of articles with nested transcript data.
    Returns:
        pd.DataFrame: Flattened DataFrame with columns for date, title, url, speaker, and text.
    """
    # Flatten transcript-level data
    rows = []
    for article in data:
        for t in article["transcript"]:
            rows.append({
                "date": parse_spanish_date(article["date"]),
                "title": article["title"],
                "url": article["url"],
                "speaker": t["speaker"],
                "text": t["text"]
            })

    df = pd.DataFrame(rows)

    # Forward fill missing speaker names
    df["speaker"] = df["speaker"].ffill()

    return df
    
def get_conference_lengths(df):
    """
    Compute length (word count) for each unique speech (title/url) and date.
    
    Args:
        df (pd.DataFrame): Must contain columns ['date', 'title', 'url', 'text']
    Returns:
        pd.DataFrame: tidy DataFrame with ['date', 'title', 'url', 'length_words']
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["text"])

    # Compute word count per paragraph
    df["word_count"] = df["text"].apply(lambda x: len(str(x).split()))

    # Aggregate by date + title + url
    result = (
        df.groupby(["date", "title", "url"], as_index=False)["word_count"]
          .sum()
          .rename(columns={"word_count": "length_words"})
          .sort_values(["date", "title"])
          .reset_index(drop=True)
    )

    #daily_lengths = (
    #    result.groupby("date", as_index=False)["length_words"].sum()
    #            .rename(columns={"length_words": "total_words_per_day"})
    #)

    return result

def get_daily_lengths(df):
    """
    Compute daily conference lengths and visualization attributes for heatmaps.

    Args:
        df (pd.DataFrame): Must contain columns ['date', 'title', 'url', 'text']
    
    Returns a tidy DataFrame with:
        - date
        - week, year, yearweek (for sorting)
        - day_of_week, day_idx (for x-axis)
        - words (total words per conference)
        - conf_rank, n_conf (for splitting same-day cells)
        - x0, x1 (for horizontal slice plotting)
    """
    # Get conference lengths
    df_lengths = get_conference_lengths(df)
    daily_split = df_lengths.copy() # to avoid modifying original
    daily_split["date"] = pd.to_datetime(daily_split["date"], errors="coerce")

    # Add week and year
    daily_split["week"] = daily_split["date"].dt.isocalendar().week
    daily_split["year"] = daily_split["date"].dt.isocalendar().year

    # Combine to get a unique "year-week" identifier
    daily_split["yearweek"] = (
        daily_split["year"].astype(str) + "-" + daily_split["week"].astype(str).str.zfill(2)
    )

    # weekday index, so we go from Monday (0) to Sunday (6)
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_to_idx = {d: i for i, d in enumerate(day_order)}
    daily_split["day_of_week"] = daily_split["date"].dt.day_name()
    daily_split["day_idx"] = daily_split["day_of_week"].map(day_to_idx)

    # rank conferences within the same date and total per date
    daily_split["conf_rank"] = daily_split.groupby("date").cumcount() + 1
    daily_split["n_conf"] = daily_split.groupby("date")["title"].transform("count")

    # compute horizontal slice bounds inside the day cell
    daily_split["x0"] = daily_split["day_idx"] + (daily_split["conf_rank"] - 1) / daily_split["n_conf"]
    daily_split["x1"] = daily_split["day_idx"] + daily_split["conf_rank"] / daily_split["n_conf"]

    # rename for clarity
    daily_split = daily_split.rename(columns={"length_words": "words"})

    return daily_split

def get_daily_lengths_by_actor(df):
    """
    Compute daily total words spoken by each actor (e.g., Presidenta vs. Periodistas),
    plus visualization attributes for heatmaps.

    Args:
        df (pd.DataFrame): Must contain at least ['date', 'speaker_clean', 'text']

    Returns:
        pd.DataFrame with columns:
            - date
            - speaker_group (actor type)
            - week, year, yearweek
            - day_of_week, day_idx
            - total words per day and actor
            - conf_rank, n_conf (for same-day split)
            - x0, x1 (for horizontal slice plotting)
    """

    # Prepare data
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Define speaker grouping
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)
    df["speaker_group"] = df["speaker_clean"].apply(
    lambda s: "Journalist" if s == "PERIODISTA/PREGUNTA" else "President/Official"
    )

    # Compute total words per date and actor
    df["words"] = df["text"].fillna("").str.split().str.len()
    daily_actor = (
        df.groupby(["date", "speaker_group"], as_index=False)["words"]
        .sum()
        .rename(columns={"words": "total_words"})
    )

    # Week and year info
    daily_actor["week"] = daily_actor["date"].dt.isocalendar().week
    daily_actor["year"] = daily_actor["date"].dt.isocalendar().year
    daily_actor["yearweek"] = (
        daily_actor["year"].astype(str) + "-" + daily_actor["week"].astype(str).str.zfill(2)
    )

    # Weekday and index for plotting
    # Asked ChatGPT to do this:
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_to_idx = {d: i for i, d in enumerate(day_order)}
    daily_actor["day_of_week"] = daily_actor["date"].dt.day_name()
    daily_actor["day_idx"] = daily_actor["day_of_week"].map(day_to_idx)

    daily_actor["month"] = daily_actor["date"].dt.strftime("%B")
    daily_actor["month"] = pd.Categorical(
        daily_actor["month"],
        categories=[
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ],
        ordered=True
    )

    # Handle multiple conferences per day
    daily_actor["conf_rank"] = daily_actor.groupby(["date", "speaker_group"]).cumcount() + 1
    daily_actor["n_conf"] = daily_actor.groupby(["date", "speaker_group"])["total_words"].transform("count")

    # Compute slice bounds (same logic as before)
    daily_actor["x0"] = daily_actor["day_idx"] + (daily_actor["conf_rank"] - 1) / daily_actor["n_conf"]
    daily_actor["x1"] = daily_actor["day_idx"] + daily_actor["conf_rank"] / daily_actor["n_conf"]

    return daily_actor

def clean_speaker(s):
    """
    Clean and standardize speaker names/labels.
    Groups related roles into unified labels.
    Args:
        s (str): Raw speaker label.
    Returns:
        str or None: Cleaned speaker label or None if to be dropped.
    """
    if pd.isna(s) or str(s).strip() == "":
        return None

    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r":$", "", s)  # remove trailing colon

    # Drop transcript markers like —000—
    if re.match(r"^[-—_ ]*0+[-—_ ]*$", s):
        return None
    # Drop administrative / non-speech labels
    if re.search(r"\(?\bFIRMA DE DECRETO\b\)?", s, re.IGNORECASE):
        return None
    if re.search(r"\(?\bFINALIZA VIDEO\b\)?", s, re.IGNORECASE):
        return None
    if re.search(r"\(?INICIA VIDEO\b\)?", s, re.IGNORECASE):
        return None
    if re.search(r"\(?Gracias\b\)?", s, re.IGNORECASE):
        return None

    # --- Group related patterns ---
    if re.match(r"^SECRETARI[AO]", s, re.IGNORECASE):
        return "SECRETARIA/SECRETARIO"
    if re.search(r"SECRETARI[AO]", s, re.IGNORECASE):
        return "SECRETARIA/SECRETARIO"
    elif re.match(r"^SUBSECRETARI[AO]", s, re.IGNORECASE):
        return "SUBSECRETARIA/SUBSECRETARIO"
    elif re.match(r"^CONSEJER[AO]", s, re.IGNORECASE):
        return "CONSEJERA/CONSEJERO"
    elif re.match(r"^PROCURADOR(A)?", s, re.IGNORECASE):
        return "PROCURADOR/PROCURADORA"
    elif re.match(r"^DIRECTOR(A)?", s, re.IGNORECASE):
        return "DIRECTOR/DIRECTORA"
    if re.search(r"DIRECTOR(A)?", s, re.IGNORECASE):
        return "DIRECTOR/DIRECTORA"
    elif re.match(r"^TITULAR(A)?", s, re.IGNORECASE):
        return "TITULAR"
    elif re.match(r"^FISCAL(A)?", s, re.IGNORECASE):
        return "FISCAL"
    elif re.match(r"^INTERLOCUTOR(A)?", s, re.IGNORECASE):
        return "INTERLOCUTOR/INTERLOCUTORA"
    elif re.match(r"^DIVULGADOR(A)?", s, re.IGNORECASE):
        return "DIVULGADOR/DIVULGADORA"
    elif re.match(r"^JEF[EA]", s, re.IGNORECASE):
        return "JRFE/JEFA"
    elif re.match(r"^COMANDANT[EA]", s, re.IGNORECASE):
        return "COMANDANTE/COMANDANTA"
    elif re.match(r"^VOCAL", s, re.IGNORECASE):
        return "VOCAL"
    elif re.match(r"^GOBERNADOR(A)?", s, re.IGNORECASE):
        return "GOBERNADOR/GOEBERNADORA"
    elif re.match(r"^COORDINADOR(A)?", s, re.IGNORECASE):
        return "COORDINADOR/COORDINADORA"
    elif re.match(r"^PRESIDENTA", s, re.IGNORECASE):
        return "CLAUDIA SHEINBAUM PARDO"
    elif re.match(r"^PREGUNTA", s, re.IGNORECASE):
        return "PERIODISTA/PREGUNTA"
    elif re.match(r"^VOZ DE (MUJER|HOMBRE)", s, re.IGNORECASE):
        return "VOZ ANÓNIMA"
    elif re.match(r"^VOZ (MUJER|HOMBRE)", s, re.IGNORECASE):
        return "VOZ ANÓNIMA"
    elif re.match(r"^INTERVENCIÓN", s, re.IGNORECASE):
        return "VOZ ANÓNIMA"
    elif re.match(r"^MODERADOR", s, re.IGNORECASE):
        return "MODERADOR"
    elif re.match(r"^[-–—_]+$", s.strip()):
        return "Unknown"
    else:
        return s
        
def get_top_speakers(df, n=20):
    """
    Return a tidy dataframe with the top N speakers across all transcripts.
    Cleans and groups speakers by common roles (e.g., SECRETARIA/SECRETARIO).
    
    Args:
        df (pd.DataFrame): Must contain a 'speaker' column.
        n (int): Number of top speakers to return.
        
    Returns:
        pd.DataFrame with columns ['speaker', 'n_speeches', 'pct_of_total']
    """

    # Apply cleaning
    df = df.copy()
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)

    # Count frequencies
    counts = (
        df["speaker_clean"]
        .dropna()
        .value_counts()
        .reset_index()
        .rename(columns={"index": "speaker", "speaker_clean": "n_speeches"})
    )
    # Compute share
    counts["pct_of_total"] = counts["count"] / counts["count"].sum()
    counts.rename(columns={'n_speeches': 'speaker'}, inplace=True)

    return counts.head(n)
        
def get_top_speakers_by_words(df, n=20):
    """
    Return a tidy dataframe with the top N speakers by total words spoken
    across all transcripts.

    Args:
        df (pd.DataFrame): Must contain 'speaker' and 'text' columns.
        n (int): Number of top speakers to return.

    Returns:
        pd.DataFrame with columns ['speaker', 'total_words', 'pct_of_total']
    """    
        
    # Apply cleaning
    df = df.copy()
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)

    # Compute word counts per intervention
    df["n_words"] = df["text"].fillna("").apply(lambda x: len(str(x).split()))

    # Aggregate by speaker
    word_stats = (
        df.groupby("speaker_clean", dropna=True)["n_words"]
        .sum()
        .reset_index()
        .rename(columns={"n_words": "total_words"})
        .sort_values("total_words", ascending=False)
    )

    # Compute shares
    total = word_stats["total_words"].sum()
    word_stats["pct_of_total"] = word_stats["total_words"] / total

    return word_stats.head(n)

def get_turn_taking_stats(df):
    """
    Compute turn-taking structure metrics for each conference.
    Args:
        df (pd.DataFrame): Must contain 'date' and 'speaker' columns.   

    Returns a tidy DataFrame with:
        - date
        - total_turns
        - president_turns
        - journalist_turns
        - ratio_president_journalist
    """
    df = df.copy()
    # Apply cleaning
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)

    # Ensure necessary columns exist
    assert "date" in df.columns and "speaker_clean" in df.columns, \
        "DataFrame must contain 'date' and 'speaker_clean' columns."

    # Group by conference date
    turn_stats = (
        df.groupby("date")
        .agg(
            total_turns=("speaker_clean", "count"),
            president_turns=("speaker_clean", lambda x: (x == "CLAUDIA SHEINBAUM PARDO").sum()),
            journalist_turns=("speaker_clean", lambda x: (x == "PERIODISTA/PREGUNTA").sum())
        )
        .reset_index()
    )

    # Compute ratio (handle division by zero)
    turn_stats["ratio_president_journalist"] = (
        turn_stats["president_turns"] / turn_stats["journalist_turns"].replace(0, pd.NA)
    )

    return  turn_stats.dropna(subset=['ratio_president_journalist'])

def get_turn_taking_stats_interact(df):
    """
    Compute turn-taking structure metrics for each conference,
    considering ONLY the conversation after the first journalist speaks.

    Args:
        df (pd.DataFrame): Must contain 'date' and 'speaker' columns.   

    Returns:
        pd.DataFrame with:
        - date
        - total_turns (after first journalist)
        - president_turns
        - journalist_turns
        - ratio_president_journalist
    """
    df = df.copy()
    # Clean speaker names
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)

    # Ensure necessary columns exist
    assert "date" in df.columns and "speaker_clean" in df.columns, \
        "DataFrame must contain 'date' and 'speaker_clean' columns."

    filtered = []

    # Loop through each conference and trim before first journalist
    for date, group in df.groupby("date"):
        group = group.reset_index(drop=True)
        # Find the first journalist index
        first_journalist_idx = group.index[group["speaker_clean"] == "PERIODISTA/PREGUNTA"]

        if len(first_journalist_idx) == 0:
            # Skip if no journalist spoke
            continue

        # Keep only rows after the first journalist intervention
        trimmed = group.loc[first_journalist_idx[0]:].copy()
        trimmed["date"] = date
        filtered.append(trimmed)

    if not filtered:
        return pd.DataFrame(columns=["date", "total_turns", "president_turns",
                                     "journalist_turns", "ratio_president_journalist"])

    df_filtered = pd.concat(filtered, ignore_index=True)

    # Compute stats
    turn_stats = (
        df_filtered.groupby("date")
        .agg(
            total_turns=("speaker_clean", "count"),
            president_turns=("speaker_clean", lambda x: (x == "CLAUDIA SHEINBAUM PARDO").sum()),
            journalist_turns=("speaker_clean", lambda x: (x == "PERIODISTA/PREGUNTA").sum())
        )
        .reset_index()
    )

    # Compute ratio
    turn_stats["ratio_president_journalist"] = (
        turn_stats["president_turns"] / turn_stats["journalist_turns"].replace(0, pd.NA)
    )

    return turn_stats.dropna(subset=['ratio_president_journalist'])

def get_avg_length_by_weekday(df):
    """
    Compute the average duration of mañaneras (in total words)
    by day of the week.

    Args:
        df (pd.DataFrame): Must contain 'date' and 'text' columns.

    Returns:
        pd.DataFrame with columns ['weekday', 'avg_words', 'n_conferences']
    """

    df = df.copy()

    # Ensure date is datetime
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Compute word count per intervention
    df["n_words"] = df["text"].fillna("").apply(lambda x: len(str(x).split()))

    # Total words per conference (sum across all speakers)
    daily_length = (
        df.groupby("date")["n_words"]
        .sum()
        .reset_index(name="total_words")
    )

    # Add weekday name
    daily_length["weekday"] = daily_length["date"].dt.day_name()

    # Average duration per weekday
    weekday_stats = (
        daily_length.groupby("weekday")
        .agg(
            avg_words=("total_words", "mean"),
            n_conferences=("total_words", "count")
        )
        .reset_index()
    )

    # Reorder weekday labels (Monday → Sunday)
    weekday_order = [
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
    ]
    weekday_stats["weekday"] = pd.Categorical(
        weekday_stats["weekday"], categories=weekday_order, ordered=True
    )
    weekday_stats = weekday_stats.sort_values("weekday")

    return weekday_stats

def clean_text(text, remove_stopwords=True, extra_stopwords=None):
    """
    Clean Spanish text for NLP analysis.

    Steps:
    1. Lowercase all text
    2. Remove accents/diacritics
    3. Strip leading/trailing whitespace
    4. Remove punctuation (including Spanish marks)
    5. Remove stopwords (Spanish)
    
    Args:
        text (str): Input text.
        remove_stopwords (bool): Whether to remove stopwords.
        extra_stopwords (list): Optional list of additional stopwords.
    
    Returns:
        str: Cleaned text string.
    """

    if not isinstance(text, str):
        return ""

    # 1. Lowercase
    text = text.lower()

    # 2. Remove accents and diacritics
    text = unidecode.unidecode(text)

    # 3. Strip whitespace
    text = text.strip()

    # 4. Remove punctuation safely
    # Define punctuation characters explicitly to avoid regex errors
    extra_punct = "¿¡…“”«»—–−–"  # Spanish marks
    all_punct = string.punctuation + extra_punct
    text = re.sub(r"[{}]".format(re.escape(all_punct)), " ", text)
    text = re.sub(r"\s+", " ", text)  # normalize spaces

    # 5. Remove stopwords
    if remove_stopwords:
        stop_words = SPANISH_STOPWORDS.copy()
        if extra_stopwords:
            stop_words.update(extra_stopwords)

        tokens = [t for t in text.split() if t not in stop_words]
        text = " ".join(tokens)

    return text

def get_topics_by_week(df, topics: dict):
    """
    Analyze topic mentions in speeches over time.
    Args:
        df (pd.DataFrame): Must contain 'date' and 'text' columns.
        topics (dict): Mapping of topic names to lists of keywords.
    Returns:
        pd.DataFrame: Tidy DataFrame with weekly topic shares and smoothed values.
    """

    # Create a copy and clean text
    pres_df = df
    pres_df["clean_text"] = pres_df["text"].apply(clean_text)
    
    def count_topic_mentions(text, topic_words):
        """Count occurrences of any topic words in the given text."""
        return sum(text.count(w) for w in topic_words)
    
    # Count mentions per topic
    topic_counts = []
    for topic, words in topics.items():
        pres_df[f"{topic}_count"] = pres_df["clean_text"].apply(lambda t: count_topic_mentions(t, words))
   
    # Aggregate daily counts
    daily_topics = pres_df.groupby("date", as_index=False)[[f"{t}_count" for t in topics]].sum()

    # Compute total words per day
    pres_df["n_words"] = pres_df["clean_text"].str.split().apply(len)
    daily_total = pres_df.groupby("date", as_index=False)["n_words"].sum()
    daily_topics = daily_topics.merge(daily_total, on="date", how="left")
    # Compute share per topic
    for topic in topics:
        daily_topics[f"{topic}_share"] = daily_topics[f"{topic}_count"] / daily_topics["n_words"]
    # Convert date to datetime and extract week/year
    daily_topics["date"] = pd.to_datetime(daily_topics["date"], errors="coerce")
    daily_topics["year"] = daily_topics["date"].dt.isocalendar().year
    daily_topics["week"] = daily_topics["date"].dt.isocalendar().week
    # Aggregate to weekly level (mean share per week)
    weekly_topics = (
        daily_topics
        .groupby(["year", "week"], as_index=False)
        .agg({col: "mean" for col in daily_topics.columns if col.endswith("_share")})
    )

    # Add a "year-week" label for easy plotting
    weekly_topics["yearweek"] = (
        weekly_topics["year"].astype(str)
        + "-W"
        + weekly_topics["week"].astype(str).str.zfill(2)
    )
    # Reshape to long format
    topic_long_weekly = weekly_topics.melt(
        id_vars=["yearweek"],
        value_vars=[col for col in weekly_topics.columns if col.endswith("_share")],
        var_name="topic",
        value_name="share"
    )
    topic_long_weekly["topic"] = topic_long_weekly["topic"].str.replace("_share", "")
    
    # Apply rolling average smoothing
    topic_long_weekly["share_smooth"] = (
        topic_long_weekly.groupby("topic")["share"].transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    return topic_long_weekly

def get_topics_by_week_by_group(df, topics: dict):
    """
    Analyze weekly topic mentions separately for each speaker group (President/Officials vs Journalists).

    Args:
        df (pd.DataFrame): Must contain 'date', 'text', and 'speaker_group' columns.
        topics (dict): Mapping of topic names to lists of keywords.

    Returns:
        pd.DataFrame: Tidy DataFrame with weekly topic shares and smoothed values by group.
    """

    # Clean text
    df = df.copy()
    df["clean_text"] = df["text"].apply(clean_text)

    def count_topic_mentions(text, topic_words):
        """Count occurrences of any topic words in the given text."""
        return sum(text.count(w) for w in topic_words)

    # Count mentions per topic
    for topic, words in topics.items():
        df[f"{topic}_count"] = df["clean_text"].apply(lambda t: count_topic_mentions(t, words))

    # Word count per intervention
    df["n_words"] = df["clean_text"].str.split().apply(len)

    # Define speaker grouping
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)
    df["speaker_group"] = df["speaker_clean"].apply(
    lambda s: "Journalist" if s == "PERIODISTA/PREGUNTA" else "President/Official"
    )

    # Aggregate daily totals by speaker group
    daily_topics = (
        df.groupby(["date", "speaker_group"], as_index=False)
        .agg({f"{t}_count": "sum" for t in topics} | {"n_words": "sum"})
    )

    # Compute topic shares
    for topic in topics:
        daily_topics[f"{topic}_share"] = daily_topics[f"{topic}_count"] / daily_topics["n_words"].replace(0, pd.NA)

    # Convert date to datetime
    daily_topics["date"] = pd.to_datetime(daily_topics["date"], errors="coerce")
    daily_topics["year"] = daily_topics["date"].dt.isocalendar().year
    daily_topics["week"] = daily_topics["date"].dt.isocalendar().week

    # Weekly averages
    weekly_topics = (
        daily_topics.groupby(["year", "week", "speaker_group"], as_index=False)
        .agg({col: "mean" for col in daily_topics.columns if col.endswith("_share")})
    )

    # Create yearweek label for plotting
    weekly_topics["yearweek"] = (
        weekly_topics["year"].astype(str)
        + "-W"
        + weekly_topics["week"].astype(str).str.zfill(2)
    )

    # Reshape to long format
    topic_long_weekly = weekly_topics.melt(
        id_vars=["yearweek", "speaker_group"],
        value_vars=[col for col in weekly_topics.columns if col.endswith("_share")],
        var_name="topic",
        value_name="share"
    )
    topic_long_weekly["topic"] = topic_long_weekly["topic"].str.replace("_share", "")

    # Rolling smoothing (per topic and group)
    topic_long_weekly["share_smooth"] = (
        topic_long_weekly.groupby(["topic", "speaker_group"])["share"]
        .transform(lambda x: x.rolling(3, min_periods=1).mean())
    )

    return topic_long_weekly

def count_state_mentions(df, text_col="text"):
    """
    Count the number of times each Mexican state is mentioned in the given text column.
    
    Args:
        df (pd.DataFrame): DataFrame containing a text column (e.g., all transcripts).
        text_col (str): Name of the column containing text data.
        
    Returns:
        pd.DataFrame: Tidy dataframe with columns ['state', 'mentions'].
    """
    # Combine all text into one large normalized string
    full_text = " ".join(df[text_col].dropna().astype(str))
    full_text = clean_text(full_text)

    results = []
    for state in MEXICO_STATES:
        # Normalize state name
        state_norm = clean_text(state)
        # Count occurrences (with word boundaries)
        pattern = r"\b" + re.escape(state_norm) + r"\b"
        count = len(re.findall(pattern, full_text))
        results.append({"state": state, "mentions": count})

    # Convert to DataFrame and sort
    df_states = pd.DataFrame(results).sort_values("mentions", ascending=False).reset_index(drop=True)
    return df_states

def count_state_mentions_by_group(df, text_col="text"):
    """
    Count the number of times each Mexican state is mentioned,
    separated by speaker group (e.g., President/Official vs Journalists).

    Args:
        df (pd.DataFrame): Must contain a text column and a speaker group column.
        text_col (str): Name of the column containing text data.

    Returns:
        pd.DataFrame: Tidy DataFrame with columns ['state', 'speaker_group', 'mentions'].
    """
    results = []

    # Ensure columns exist
    assert text_col in df.columns, f"Missing text column: {text_col}"

    # Define speaker grouping
    df["speaker_clean"] = df["speaker"].apply(clean_speaker)
    df["speaker_group"] = df["speaker_clean"].apply(
    lambda s: "Journalist" if s == "PERIODISTA/PREGUNTA" else "President/Official"
    )

    # Loop through each group (President/Official vs Journalist)
    for group, subset in df.groupby("speaker_group"):
        # Combine and clean all text for that group
        full_text = " ".join(subset[text_col].dropna().astype(str))
        full_text = clean_text(full_text)

        for state in MEXICO_STATES:
            state_norm = clean_text(state)
            pattern = r"\b" + re.escape(state_norm) + r"\b"
            count = len(re.findall(pattern, full_text))
            results.append({
                "state": state,
                "speaker_group": group,
                "mentions": count
            })

    df_states = (
        pd.DataFrame(results)
        .sort_values(["speaker_group", "mentions"], ascending=[True, False])
        .reset_index(drop=True)
    )

    return df_states

def normalize_name(name):
    """
    Normalize Mexican state names for matching.
    Args:
        name (str): Raw state name.
    Returns:
        str: Normalized state name.
    """
    name = ''.join(
        c for c in unicodedata.normalize('NFD', str(name))
        if unicodedata.category(c) != 'Mn'
    )
    return name.lower().replace(" de ignacio de la llave", "").replace(" de zaragoza", "").strip()

def _predict_sentiment(text: str) -> tuple[str, float, dict]:
    """
    Return (label, score, probas_dict) using pysentimiento.
    label in {'POS','NEU','NEG'}
    score is mapped to {1,0,-1}
    """
    if not isinstance(text, str) or not text.strip():
        return "NEU", 0.0, {"POS": 0.0, "NEU": 1.0, "NEG": 0.0}
    pred = _analyzer_es.predict(text)
    label = pred.output  # 'POS' | 'NEU' | 'NEG'
    score = _LABEL_TO_SCORE[label]
    return label, score, pred.probas  # dict like {'NEG': p1, 'NEU': p2, 'POS': p3}

def compute_sentiment_for_date(
    df: pd.DataFrame,
    target_date: str,
    *,
    text_col: str = "text",
    date_col: str = "date",
    speaker_col: str = "speaker_group",
    keep_columns: Optional[list[str]] = None,
    after_first_journalist: bool = True
) -> pd.DataFrame:
    """
    Filter a single conference (date == target_date), compute sentiment per intervention.

    If after_first_journalist=True, only keeps interventions after the first journalist speaks.

    Returns a tidy DataFrame with:
      - date
      - intervention_order (1..n)
      - speaker_group (President/Official or Journalist)
      - text
      - sentiment_label (Positive / Neutral / Negative)
      - sentiment_score (1 / 0 / -1)
      - p_pos, p_neu, p_neg (model probabilities)
    """
    if _analyzer_es is None:
        raise RuntimeError("Spanish sentiment analyzer not available. "
                           "Install/verify pysentimiento, transformers, and torch.")

    # 1) Filter that single conference
    d = df.copy()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    target_dt = pd.to_datetime(target_date)
    conf = d.loc[d[date_col] == target_dt].copy()

    if conf.empty:
        return pd.DataFrame(columns=[
            date_col, "intervention_order", speaker_col, text_col,
            "sentiment_label", "sentiment_score", "p_pos", "p_neu", "p_neg", "speaker_group"
        ])

    # 2) Preserve original sequence
    conf = conf.reset_index(drop=True)
    conf["intervention_order"] = conf.index + 1

    # 3) Speaker grouping
    if "speaker_clean" not in conf.columns:
        conf["speaker_clean"] = conf["speaker"].apply(clean_speaker)

    conf["speaker_group"] = conf["speaker_clean"].apply(
        lambda s: "Journalist" if s == "PERIODISTA/PREGUNTA" else "President/Official"
    )

    # 4) Keep only after first journalist if requested
    if after_first_journalist:
        first_journalist_idx = conf.index[conf["speaker_group"] == "Journalist"]
        if len(first_journalist_idx) > 0:
            start_idx = first_journalist_idx[0]
            conf = conf.loc[start_idx:].reset_index(drop=True)
            conf["intervention_order"] = conf.index + 1

    # 5) Run sentiment analysis
    labels, scores, p_pos, p_neu, p_neg = [], [], [], [], []
    for txt in conf[text_col].fillna("").astype(str):
        lab, sc, prob = _predict_sentiment(txt)
        labels.append(_SPANISH_LABEL[lab])
        scores.append(sc)
        p_pos.append(prob.get("POS", 0.0))
        p_neu.append(prob.get("NEU", 0.0))
        p_neg.append(prob.get("NEG", 0.0))

    conf["sentiment_label"] = labels
    conf["sentiment_score"] = scores
    conf["p_pos"] = p_pos
    conf["p_neu"] = p_neu
    conf["p_neg"] = p_neg

    # 6) Select columns
    base_cols = [
        date_col, "intervention_order", speaker_col, text_col,
        "sentiment_label", "sentiment_score", "p_pos", "p_neu", "p_neg", "speaker_group"
    ]
    if keep_columns:
        extra = [c for c in keep_columns if c in conf.columns and c not in base_cols]
        base_cols += extra

    return conf[base_cols]
