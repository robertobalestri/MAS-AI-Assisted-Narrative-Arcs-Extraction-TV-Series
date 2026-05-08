# Narrative Arc Analysis System

A Python-based system for extracting, analyzing and visualizing narrative arcs from TV series plots, with a React-based frontend for visualization and management.

## Features

- Extract and analyze narrative arcs from episode plots
- Process character entities and relationships
- Generate semantic plot segments
- Visualize narrative arc relationships and clusters
- Interactive web interface for managing arcs and characters
- Vector store for semantic search and similarity analysis

## Prerequisites

- Python 3.8+
- Node.js 16+
- SQLite
- Azure OpenAI API access
- Cohere API access

## Installation

1. Clone the repository:

```
pip install -r requirements.txt
```

Install the frontend node modules from the `frontend` folder.

Start the backend API with `uvicorn api.api_main:app --reload`.

Then, from the `frontend` folder, run `npm run dev`.

Series analysis is now triggered from the frontend through the backend.