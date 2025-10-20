# Mapping the Narrative: Thematic Trends in Claudia Sheinbaum’s Daily Press Conferences

José Manuel Cardona Arias

## What is your current goal? Has it changed since the proposal?

My goal remains consistent with the original proposal: to visually explore the characteristics, dominant themes and evolving narrative patterns in President Claudia Sheibaum's daily press conferences ("Las mañaneras del pueblo"). The focus is still on uncovering how the presidential discourse frames political priorities, constructs public narratives, and reacts to major national events. 

Some things I have expanded:
- I have expanded the data pipeline to include automated web scraping, text processing, and speaker-level analysis.
- Beyond topic trends, I am now also exploring descriptive dimensions such as conference duration, participation by speaker type (Presidenta, periodistas, secretarios, etc.), and the geographic focus of the discussions through mentions of Mexican states.

## Are there data challenges you are facing? Are you currently depending on mock data?
There have been significant data engineering challenges, though I am now working with real data successfully scraped from the official Blog de la Presidencia website. 

Challenges encountered cover:
- The website’s HTML structure is inconsistent, requiring robust parsing and retry logic to handle timeouts and malformed entries.
- Transcripts are formatted paragraph by paragraph, which demanded additional logic to correctly reconstruct speaker turns and identify who is speaking at each point.
- Some metadata (dates, speaker names) required heavy cleaning and normalization (e.g., standardizing date formats and grouping roles like “SECRETARIA” / “SECRETARIO”).
  
Current status:
- I now have a comprehensive JSON dataset containing all conferences since Sheinbaum took office, including metadata (date, title, URL, speaker, and text).
- The dataset has been cleaned and transformed into smaller and tidy dataframes.
- No mock data are currently used — all analyses are based on real transcripts obtained directly from the government’s website.

## Describe each of the provided images with 2-3 sentences to give the context and how it relates to your goal.

### 1. Length of Claudia Sheinbaum’s Conferences
This visualization explores how the length of the mañaneras varies by weekday and week. By measuring the number of words spoken each day, it reveals patterns in the president’s communication rhythm.

![Heatmap of conference length]()

### 2. Conference length by weekday
The goal of this visualization is to analyze the lenght of the conferences by week and weekday. This visualization allows to distinguish by days with multiple conferences.

### 3. Top speakers at the conferences
This visualization identifies the top speakers during the mañaneras based on the number of interventions. It highlights how participation is distributed among different actors, offering insight into the dynamics of who speaks most often during the daily conferences.

### 4. Top speakers at the conferences by number of words
This visualization highlights the top speakers during the mañaneras based on both the frequency and length of their interventions. By combining how often each actor speaks with how much they speak, it reveals differences in participation dynamics. Showing not only who takes the floor most frequently, but also who dominates the discussion in terms of total words spoken.

### 5. Turn-taking structure of conferences by time. 
This visualization examines the turn-taking structure of the mañaneras, focusing on how speaking time is shared between the President and journalists.

### 6. Turn-taking structure of conferences by time. 
This visualization explores the turn-taking structure of the mañaneras by analyzing the percentage of total speaking turns taken by the President, journalists, and other participants over time.

### 7. Average length by weekday
This visualization analyzes the average length of the mañaneras by weekday to identify patterns in their duration. It helps reveal whether certain days of the week consistently feature longer or shorter conferences.

### 8. Topic occurence by week
This visualization tracks the weekly occurrence of key topics in the mañaneras to show how the president’s focus shifts over time. By grouping mentions of themes such as education, migration, or security by week, it highlights changing priorities and the evolving narrative of government discourse.

### 9. What states in Mexico are mentioned the most?
This visualization examines which Mexican states are mentioned most frequently during the mañaneras. By counting references to each state across all conferences, it reveals the geographic focus of the president’s discourse.

## What form do you envision your final narrative taking? (e.g. An article incorporating the images? A poster? An infographic?)

I think my final narrative will take the form of an interactive data story; a web-based article that combines narrative text with dynamic visualizations.
