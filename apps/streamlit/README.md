# Streamlit Branch Workspace

This folder is fully isolated from the root React/Vite app.

## Branch naming rule
- `feature/streamlit-workflow-YYMMDD`
- Example for 2026-02-25: `feature/streamlit-workflow-260225`

## Setup (Windows PowerShell)
```powershell
cd apps/streamlit
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Implemented scope
1. Load sample workflow in one click
2. Create nodes from templates at any time
3. Connect nodes with horizontal/vertical/parallel modes
4. Allow multiple edges between same node pairs
5. Run node actions:
- Reference Input
- Raw Translate
- Sentence Normalize
- Extract/Highlight
- Theory Build
- Research Question Generate/Approve
- Methodology Build
6. Methodology lock rules:
- At least one approved research question
- At least one category artifact
- At least three evidence links

## Folder structure
- `app.py`: Streamlit entrypoint
- `core/pipeline.py`: node templates, initial nodes/edges
- `core/state.py`: session state, status/lock computation
- `core/sample_data.py`: sample workflow payload
- `core/actions.py`: node execution and editing actions
- `components/canvas.py`: SVG canvas renderer
- `components/panels.py`: builder/status/log panels
- `services/api_client.py`: mock/real adapter with token masking
