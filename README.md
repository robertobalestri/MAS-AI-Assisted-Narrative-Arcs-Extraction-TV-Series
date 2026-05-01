# Multi-Agent System for AI-Assisted Extraction

## Setup Instructions

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Environment Configuration:
   - Copy `.env.example` to `.env`
   - Currently supported configurations:
     - Azure OpenAI (for LLM)
     - Azure Cohere (for embeddings)
   - Fill in your API keys and endpoints in the `.env` file

3. Frontend Setup:
```bash
cd frontend
npm install
```

## Data Structure Requirements

Your data should be organized as follows:

```
data/
└── SERIES
    └── SEASON
        └── EPISODE
            plot.txt files named as SERIESSXXEXX_plot.txt
            where SERIES is the series identifier (e.g., GA for Grey's Anatomy)
            and XX represents the season and episode numbers
            Example: GAS01E01_plot.txt, GAS01E02_plot.txt, etc.
```

with Grey's Anatomy Season 1 as an example:

```
data/
└── GA
    └── S01
        └── E01
            GAS01E01_plot.txt
        └── E02
            GAS01E02_plot.txt
```

Each `plot.txt` file should contain the episode's plot description.

## Pre-filled Data

The current codebase includes:
- A pre-filled database and vector store containing the first season of Grey's Anatomy (GA)
- You can use this as a reference for how to structure your own data
- The existing Grey's Anatomy episodes follow the naming convention: GAS01E01_plot.txt, GAS01E02_plot.txt, etc. along with other system's generated files for the analysis.

## Running the Application

1. Start the analysis with the terminal:
```bash
python main.py
```

Wait for its completion.

When it's done, you can open the web interface to explore the results: first start the API server:
```bash
uvicorn api.api_main:app --reload
```
Then start the frontend from the frontend folder:
```bash
npm run dev
```

## Note
Currently, the system only supports Azure OpenAI for LLM operations and Azure Cohere for embeddings. Support for other providers may be added in future updates.