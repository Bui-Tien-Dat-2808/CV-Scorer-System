# core/constants.py

LANGUAGES = [
    'python', 'java', 'c#', 'c++', 'c', 'javascript', 'typescript', 'php', 'ruby',
    'go', 'golang', 'swift', 'kotlin', 'sql', 'dart', 'rust', 'scala', 'r'
]

DATABASES = [
    'mysql', 'postgresql', 'postgres', 'mongodb', 'redis', 'sqlite', 'oracle',
    'sql server', 'mssql', 'firebase', 'elasticsearch', 'cassandra', 'neo4j',
    'qdrant', 'milvus', 'chroma', 'pinecone', 'dynamodb'
]

FRAMEWORKS = [
    'react', 'reactjs', 'angular', 'vue', 'vuejs', 'node.js', 'nodejs', 'express',
    'django', 'flask', 'fastapi', 'spring boot', 'spring', 'flutter', 'react native',
    'next.js', 'nextjs', 'nest.js', 'nestjs', 'laravel', 'asp.net', '.net'
]

AI_ML_SKILLS = [
    'pytorch', 'tensorflow', 'keras', 'scikit-learn', 'sklearn', 'opencv',
    'huggingface', 'transformers', 'langchain', 'llamaindex', 'rag',
    'deep learning', 'machine learning', 'nlp', 'llm', 'computer vision',
    'genai', 'generative ai', 'prompt engineering', 'fine-tuning'
]

DEVOPS_TOOLS = [
    'docker', 'kubernetes', 'k8s', 'git', 'github', 'gitlab', 'ci/cd',
    'aws', 'gcp', 'azure', 'linux', 'bash', 'terraform', 'ansible',
    'kafka', 'spark', 'airflow', 'grafana', 'prometheus'
]

EDUCATION_LEVELS = [
    'phd', 'doctorate', 'master', 'mba', 'bachelor', 'engineer', 'university', 'associate', 'college'
]

EDUCATION_RANKING = {
    'Phd': 4, 'Doctorate': 4,
    'Master': 3, 'Mba': 3,
    'Bachelor': 2, 'Engineer': 2, 'University': 2,
    'Associate': 1, 'College': 1,
    'None': 0
}

SKILL_LEVEL_MAPPING = {
    # Level 3: Senior / Expert
    'senior': 3, 'expert': 3, 'advanced': 3, 'lead': 3, 'principal': 3, 
    'xuất sắc': 3, 'thành thạo': 3, 'chuyên sâu': 3, 'master': 3, 'strong': 3,

    # Level 2: Mid / Intermediate
    'intermediate': 2, 'proficient': 2, 'good': 2, 'experienced': 2, 
    'khá': 2, 'biết': 2, 'sử dụng tốt': 2, 'solid': 2, 'middle': 2, 'mid': 2,

    # Level 1: Junior / Basic
    'junior': 1, 'basic': 1, 'familiar': 1, 'beginner': 1, 'fresher': 1, 
    'cơ bản': 1, 'mới': 1, 'nhập môn': 1, 'tập sự': 1
}

# Bảng tra từ đồng nghĩa kỹ thuật (Alias normalization)
SKILL_ALIASES = {
    'js': 'javascript',
    'ts': 'typescript',
    'golang': 'go',
    'postgres': 'postgresql',
    'mssql': 'sql server',
    'k8s': 'kubernetes',
    'tf': 'tensorflow',
    'sklearn': 'scikit-learn',
    'genai': 'generative ai',
    'ml': 'machine learning',
    'dl': 'deep learning',
    'reactjs': 'react',
    'vuejs': 'vue',
    'nextjs': 'next.js',
    'nodejs': 'node.js',
    'nestjs': 'nest.js'
}

# Từ khóa loại trừ khi bóc tách tên ứng viên
NAME_IGNORE_KEYWORDS = [
    "curriculum", "vitae", "resume", "profile", "contact", "developer", "engineer",
    "experience", "education", "skills", "summary", "objective", "projects", "certifications",
    "họ và tên", "thông tin", "kinh nghiệm", "kỹ năng", "mục tiêu", "portfolio"
]
