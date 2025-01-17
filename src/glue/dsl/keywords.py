# src/glue/dsl/keywords.py

"""GLUE DSL Keyword Mappings"""

# Model Provider Keywords
PROVIDER_KEYWORDS = {
    # Model Providers
    'openrouter': 'openrouter',
    'anthropic': 'anthropic',
    'groq': 'groq',
    'mistral': 'mistral',
    'llama': 'llama',
    
    # Search Providers
    'serp': 'serp',
    'serpapi': 'serp',
    'tavily': 'tavily',
    'bing': 'bing',
    'you': 'you'
}

# Configuration Keywords
CONFIG_KEYWORDS = {
    # API Configuration
    'api': 'api_key',
    'key': 'api_key',
    'token': 'api_key',
    'api_key': 'api_key',
    'os.api_key': 'api_key',
    'os.key': 'api_key',
    'os.serp_api_key': 'api_key',
    'os.serpapi_key': 'api_key',
    'os.tavily_api_key': 'api_key',
    'os.bing_api_key': 'api_key',
    'os.you_api_key': 'api_key',
    
    # Model Configuration
    'temperature': 'temperature',
    'temp': 'temperature',
    'top_p': 'top_p',
    'sampling': 'top_p',
    'max_tokens': 'max_tokens',
    'length': 'max_tokens',
    'limit': 'max_tokens',
    
    # Memory Configuration
    'memory': 'memory',
    'context': 'memory',
    'history': 'memory',
    'recall': 'memory',
    'remember': 'memory',
    
    # Tool Configuration
    'tools': 'tools',
    'tool': 'tools',
    'uses': 'tools',
    'access': 'tools',
    
    # Persistence Configuration
    'sticky': 'sticky',
    'persist': 'sticky',
    'save': 'sticky',
    'remember': 'sticky',
    
    # Magnetic Configuration
    'magnetic': 'magnetic',
    'attract': 'magnetic',
    'field': 'magnetic',
    'magnetize': 'magnetic',
    
    # Development Configuration
    'development': 'development',
    'dev': 'development',
    'debug': 'development',
    
    # Chain Configuration
    'chain': 'chain',
    'sequence': 'chain',
    'pipeline': 'chain',
    'double_side_tape': 'chain'
}

# Operation Keywords
OPERATION_KEYWORDS = {
    # Workflow Operations
    'workflow': 'workflow',
    'attract': 'attract',
    'repel': 'repel',
    
    # Magnetic Operators
    '><': 'attract_op',  # Attraction operator
    '<>': 'repel_op',    # Repulsion operator
    
    # Flow Control
    'if': 'condition',
    'when': 'condition',
    'unless': 'negative_condition',
    'else': 'alternative',
    'then': 'sequence'
}

ROLE_KEYWORDS = {
    'role': 'role',
    'system': 'role',
    'prompt': 'role',
    'instruction': 'role'
}

# Application Keywords
APP_KEYWORDS = {
    # App Definition
    'app': 'app',
    'application': 'app',
    'glue': 'app',
    'glue_app': 'app',
    'agent': 'app',
    'title': 'name',  # Add this for alternative syntax
    'components': 'tools',  # Add this for alternative syntax
    
    # App Configuration
    'name': 'name',
    'title': 'name',
    'description': 'description',
    'about': 'description',
    'version': 'version',
    
    # App Components
    'model': 'model',
    'tool': 'tool',
    'config': 'config'
}

def get_keyword_type(keyword: str) -> tuple[str, str]:
    """Get the type and normalized value for a keyword"""
    keyword = keyword.lower()
    
    # Special cases for app blocks
    if keyword in ['glue app', 'application']:
        return 'app', 'app'
        
    # Handle role variations
    if '_role' in keyword or '_system' in keyword or '_prompt' in keyword or \
       '_instruction' in keyword or '_behavior' in keyword or '_personality' in keyword:
        return 'role', 'role'
    
    # Check each keyword mapping
    if keyword in ROLE_KEYWORDS:
        return 'role', ROLE_KEYWORDS[keyword]
    elif keyword in PROVIDER_KEYWORDS:
        return 'provider', PROVIDER_KEYWORDS[keyword]
    elif keyword in CONFIG_KEYWORDS:
        return 'config', CONFIG_KEYWORDS[keyword]
    elif keyword in OPERATION_KEYWORDS:
        return 'operation', OPERATION_KEYWORDS[keyword]
    elif keyword in APP_KEYWORDS:
        return 'app', APP_KEYWORDS[keyword]
    
    return 'unknown', keyword
