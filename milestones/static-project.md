# José Manuel Cardona Arias

## Project title
Mapping the Narrative: Thematic Trends in Claudia Sheinbaum’s Daily Press Conferences

## Description

I want to visually explore the dominant themes and evolving narrative patterns in President Claudia Sheinbaum’s daily press conferences, commonly known as “las mañaneras del pueblo.” These morning conferences, held every weekday, serve as the Mexican government’s main communication channel with the public. Here, the president sets the national agenda, frames political narratives, and responds directly to journalists. By analyzing the frequency and co-occurrence of key topics within these addresses, the project seeks to uncover how presidential discourse articulates public priorities, constructs collective identity, and reacts to major national events, offering insight into how political messaging shapes public perception in contemporary Mexico.

I am particularly interested in working with this data and potentially developing a useful and accessible tool because I often find it difficult to keep up with all the press conferences. At times, I feel a sense of responsibility for not staying fully informed about the political climate in my own country, and this project represents a way to bridge that gap through data and visualization.

## Data Sources

### Data Source 1: [Blog de la Presidencia de la República](https://www.gob.mx/presidencia/es/archivo/articulos?filter_origin=archive&idiom=es&order=DESC&page=1)

Size: Since Clauda Sheibaum bacame president of Mexico, she has done a press conference daily. The President's team publishes official stenographic transcripts. I aim to analize all conferences between October 1st 2024 and October 1st 2025.

Processing:
Creating a dataset ready to visualize will require several key stages of data engineering and natural language preprocessing:

1. Web Scraping: Automate the extraction of all available conference pages. Collect metadata (date, title, URL, length, participants) and full transcript text. Store data in a structured format (e.g., CSV or JSON).

2. Text Cleaning and Standardization: Remove HTML tags, speaker labels. Normalize text. Optionally, separate content by speaker (President vs. journalists).

3. Tokenization and Lemmatization

4. Thematic Tagging and Topic Grouping

6. Sentiment or Tone Analysis (TBD)


## Questions

1. Would you encourage incorporating methods like topic modeling or sentiment analysis, or should I keep the focus strictly on visualization?
2. Given the course timeline, what would be a reasonable scope for a text-based visualization project like this?
