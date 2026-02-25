from copy import deepcopy

API_PROVIDERS = ["openai", "claude", "gemini", "custom"]
CATEGORIES = ["core-concept", "methodology", "result", "limitation", "citable-claim"]
METHOD_TEMPLATES = ["qualitative", "quantitative", "mixed", "concept-analysis"]

CORE_NODE_IDS = {
    "REF": "n-ref-input",
    "RAW": "n-raw-translate",
    "NORM": "n-sentence-normalize",
    "EXTRACT": "n-sentence-extract",
    "THEORY": "n-theory-builder",
    "QUESTION": "n-rq-generator",
    "METHOD": "n-methodology",
}

NODE_TEMPLATES = [
    {
        "type": "reference",
        "icon": "database",
        "label": "Reference Input Node",
        "desc": "Upload/URL + metadata extraction",
    },
    {
        "type": "translate",
        "icon": "cpu",
        "label": "Raw Translate Node",
        "desc": "Original language to work language",
    },
    {
        "type": "normalize",
        "icon": "settings",
        "label": "Sentence Normalization Node",
        "desc": "Sentence split/alignment/cleanup",
    },
    {
        "type": "extract",
        "icon": "box",
        "label": "Sentence Extract & Highlight Node",
        "desc": "Highlight + extract + edit artifacts",
    },
    {
        "type": "theory",
        "icon": "brain",
        "label": "Theoretical Background Builder Node",
        "desc": "Category tree + evidence snapshot",
    },
    {
        "type": "question",
        "icon": "search",
        "label": "Research Question Generator Node",
        "desc": "Auto/manual/review tabs",
    },
    {
        "type": "methodology",
        "icon": "branch",
        "label": "Methodology Node",
        "desc": "Locked until approved evidence path",
    },
]

INITIAL_NODES = [
    {
        "id": CORE_NODE_IDS["REF"],
        "x": 40,
        "y": 200,
        "icon": "database",
        "label": "Reference Input Node",
        "desc": "Upload/URL + metadata extraction",
        "type": "reference",
        "status": "ready",
    },
    {
        "id": CORE_NODE_IDS["RAW"],
        "x": 350,
        "y": 200,
        "icon": "cpu",
        "label": "Raw Translate Node",
        "desc": "Original language to work language",
        "type": "translate",
        "status": "idle",
    },
    {
        "id": CORE_NODE_IDS["NORM"],
        "x": 660,
        "y": 200,
        "icon": "settings",
        "label": "Sentence Normalization Node",
        "desc": "Sentence split/alignment/cleanup",
        "type": "normalize",
        "status": "idle",
    },
    {
        "id": CORE_NODE_IDS["EXTRACT"],
        "x": 970,
        "y": 200,
        "icon": "box",
        "label": "Sentence Extract & Highlight Node",
        "desc": "Highlight + extract + edit artifacts",
        "type": "extract",
        "status": "idle",
    },
    {
        "id": CORE_NODE_IDS["THEORY"],
        "x": 1280,
        "y": 200,
        "icon": "brain",
        "label": "Theoretical Background Builder Node",
        "desc": "Category tree + evidence snapshot",
        "type": "theory",
        "status": "idle",
    },
    {
        "id": CORE_NODE_IDS["QUESTION"],
        "x": 1590,
        "y": 200,
        "icon": "search",
        "label": "Research Question Generator Node",
        "desc": "Auto/manual/review tabs",
        "type": "question",
        "status": "idle",
    },
    {
        "id": CORE_NODE_IDS["METHOD"],
        "x": 1900,
        "y": 200,
        "icon": "branch",
        "label": "Methodology Node",
        "desc": "Locked until approved evidence path",
        "type": "methodology",
        "status": "idle",
    },
]

INITIAL_EDGES = [
    {"id": "e1", "from_id": CORE_NODE_IDS["REF"], "to_id": CORE_NODE_IDS["RAW"], "label": "rawText", "mode": "horizontal"},
    {"id": "e2", "from_id": CORE_NODE_IDS["RAW"], "to_id": CORE_NODE_IDS["NORM"], "label": "translatedText", "mode": "horizontal"},
    {"id": "e3", "from_id": CORE_NODE_IDS["NORM"], "to_id": CORE_NODE_IDS["EXTRACT"], "label": "sentenceUnits", "mode": "horizontal"},
    {"id": "e4", "from_id": CORE_NODE_IDS["EXTRACT"], "to_id": CORE_NODE_IDS["THEORY"], "label": "sentenceArtifacts", "mode": "horizontal"},
    {"id": "e5", "from_id": CORE_NODE_IDS["THEORY"], "to_id": CORE_NODE_IDS["QUESTION"], "label": "theorySupport", "mode": "horizontal"},
    {"id": "e6", "from_id": CORE_NODE_IDS["QUESTION"], "to_id": CORE_NODE_IDS["METHOD"], "label": "approvedRQ", "mode": "horizontal"},
]

CORE_TYPE_ORDER = [
    "reference",
    "translate",
    "normalize",
    "extract",
    "theory",
    "question",
    "methodology",
]


def clone_initial_nodes():
    return deepcopy(INITIAL_NODES)


def clone_initial_edges():
    return deepcopy(INITIAL_EDGES)


def get_template_map():
    return {template["type"]: template for template in NODE_TEMPLATES}
