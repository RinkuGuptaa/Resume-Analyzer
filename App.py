import os
from flask import Flask, render_template, request
import PyPDF2
import docx
import io
import re # For regular expressions
import spacy
from spellchecker import SpellChecker # For spell checking
import textstat # For readability
from datetime import datetime # For current year in footer

# --- Configuration ---
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If the model is not found, it's a setup issue for a deployed app.
    # The original RuntimeError is good. The print/download lines were unreachable.
    raise RuntimeError(
        "spaCy model 'en_core_web_sm' not found. "
        "Ensure it is included in your deployment environment (e.g., in build steps or requirements)."
    )

app = Flask(__name__)
# It's good practice to get configurations from environment variables in production
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Ensure upload folder exists (optional, consider if needed in a stateless environment)
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- Helper Functions for Text Extraction ---
def extract_text_from_pdf(file_stream):
    text = ""
    try:
        reader = PyPDF2.PdfReader(file_stream)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        return None, f"Error reading PDF: {str(e)}"
    return text, None

def extract_text_from_docx(file_stream):
    text = ""
    try:
        doc = docx.Document(file_stream)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        return None, f"Error reading DOCX: {str(e)}"
    return text, None

# --- Individual Analysis Functions (Using the second, more complete set from your original code) ---
# Ensure this is the set of functions you intend to use.
# The first set of definitions that appeared before the original line 817 should be removed.

def check_contact_info(text):
    feedback = []
    score_data = {'email_found': False, 'phone_found': False, 'linkedin_found': False}
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    phone_pattern = r"(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})" # Simple US-like

    if re.search(email_pattern, text):
        feedback.append("Good: Email address detected.")
        score_data['email_found'] = True
    else:
        feedback.append("Suggestion (High Priority): Email address not found or in an unrecognized format. Ensure it's clearly visible.")

    if re.search(phone_pattern, text):
        feedback.append("Good: Phone number detected.")
        score_data['phone_found'] = True
    else:
        feedback.append("Suggestion (High Priority): Phone number not found or in an unrecognized format. Ensure it's clearly visible.")

    if "linkedin.com/in/" in text.lower() or "linkedin.com/pub/" in text.lower():
        feedback.append("Good: LinkedIn profile link seems to be present.")
        score_data['linkedin_found'] = True
    else:
        feedback.append("Suggestion: Consider adding a link to your LinkedIn profile for networking and professional presence.")
    return feedback, score_data

def check_section_headings(text):
    feedback = []
    text_lower = text.lower()
    required_sections_map = {
        "summary": ["summary", "profile", "objective", "about me"],
        "experience": ["experience", "work experience", "professional experience", "employment history"],
        "education": ["education", "academic background", "qualifications"],
        "skills": ["skills", "technical skills", "proficiencies", "expertise", "technologies"]
    }
    optional_sections = ["projects", "awards", "publications", "volunteer", "certifications", "portfolio", "references", "languages"]
    found_required_count = 0

    for key, variations in required_sections_map.items():
        if any(variation in text_lower for variation in variations):
            feedback.append(f"Good: Section '{key.capitalize()}' seems to be present.")
            found_required_count += 1
        else:
            feedback.append(f"Suggestion: Missing a clear '{key.capitalize()}' section. This is a standard resume component.")

    if found_required_count < len(required_sections_map):
        feedback.append("Warning: Some standard sections (Summary, Experience, Education, Skills) might be missing or not clearly labeled. Ensure these are easily identifiable.")

    for section in optional_sections:
        if section in text_lower:
            feedback.append(f"Info: Optional section '{section.capitalize()}' detected. Ensure it adds value.")
    score_data = {'required_sections_found': found_required_count, 'total_required_sections': len(required_sections_map)}
    return feedback, score_data

def check_resume_length(text):
    feedback = []
    word_count = len(text.split())
    feedback.append(f"Info: Total word count is approximately {word_count}.")
    length_ok = True
    if word_count < 250:
        feedback.append("Suggestion: Your resume seems quite short (less than 250 words). Consider adding more detail, accomplishments, or relevant projects, especially if you have more than a year or two of experience.")
        length_ok = False
    elif word_count > 800: # Roughly > 2 pages for most standard formatting
        feedback.append("Suggestion: Your resume might be too long (over 800 words). Aim for conciseness. For most professionals, 1-2 pages is ideal. Focus on the most relevant information for the jobs you're targeting.")
        length_ok = False
    elif word_count > 500 and word_count <= 800:
        feedback.append("Info: Resume length seems appropriate for many roles (500-800 words). Ensure it's concise and impactful.")
    else: # 250-500 words
        feedback.append("Info: Resume length is reasonable (250-500 words), especially for early-career professionals. Ensure you've included enough detail for your experience level.")
    score_data = {'word_count': word_count, 'length_ok': length_ok}
    return feedback, score_data

def check_action_verbs(doc):
    feedback = []
    # Using the more comprehensive list from your first definition
    action_verbs_list = [
        "accelerated", "achieved", "acquired", "adapted", "administered", "advanced", "advised", "advocated", "aided", "allocated", "analyzed", "anticipated", "applied", "appraised", "approved", "arbitrated", "arranged", "articulated", "assembled", "assessed", "assigned", "assisted", "attained", "audited", "augmented", "authored", "authorized", "automated", "awarded",
        "balanced", "benchmarked", "boosted", "briefed", "broadened", "budgeted", "built",
        "calculated", "cataloged", "centralized", "chaired", "championed", "changed", "clarified", "classified", "coached", "coded", "collaborated", "collected", "combined", "comforted", "commanded", "communicated", "compared", "compiled", "completed", "composed", "computed", "conceived", "conceptualized", "condensed", "conducted", "configured", "conserved", "consolidated", "constructed", "consulted", "contacted", "contributed", "controlled", "converted", "convinced", "cooperated", "coordinated", "corrected", "corresponded", "counseled", "created", "critiqued", "cultivated", "customized", "cut",
        "debugged", "decentralized", "decreased", "dedicated", "deduced", "defined", "delegated", "delivered", "demonstrated", "designed", "detected", "determined", "developed", "devised", "diagnosed", "differentiated", "directed", "disciplined", "discovered", "dispensed", "displayed", "disproved", "dissected", "distributed", "diversified", "documented", "doubled", "drafted", "dramatized",
        "earned", "edited", "educated", "effected", "elicited", "eliminated", "enabled", "encouraged", "endorsed", "engineered", "enhanced", "enlarged", "enlisted", "ensured", "entertained", "established", "estimated", "evaluated", "examined", "exceeded", "executed", "exercised", "exhibited", "expanded", "expedited", "experimented", "explained", "explored", "expressed", "extended", "extracted",
        "fabricated", "facilitated", "familiarized", "fashioned", "filed", "financed", "fixed", "focused", "forecasted", "formalized", "formed", "formulated", "fostered", "founded", "framed", "fulfilled", "functioned", "furnished",
        "gained", "gathered", "gauged", "generated", "governed", "graded", "granted", "greeted", "grouped", "grew", "guided",
        "halved", "handled", "harmonized", "harnessed", "headed", "helped", "hired", "hosted", "hypothesized",
        "identified", "ignited", "illustrated", "imagined", "implemented", "improved", "improvised", "inaugurated", "incorporated", "increased", "indexed", "indicated", "individualized", "induced", "influenced", "informed", "initiated", "innovated", "inspected", "inspired", "installed", "instigated", "instituted", "instructed", "insured", "integrated", "intensified", "interacted", "interpreted", "interviewed", "introduced", "invented", "inventoried", "invested", "investigated", "involved", "isolated", "issued",
        "joined", "judged", "justified",
        "kept",
        "launched", "learned", "lectured", "led", "licensed", "listened", "lobbied", "localized", "located", "logged",
        "machined", "made", "maintained", "managed", "manipulated", "manufactured", "mapped", "marketed", "mastered", "maximized", "measured", "mediated", "mentored", "merged", "met", "minimized", "mobilized", "modeled", "moderated", "modernized", "modified", "molded", "monitored", "motivated", "moved", "multiplied",
        "narrated", "navigated", "negotiated", "networked", "neutralized", "nominated", "normalized", "notified", "nurtured",
        "observed", "obtained", "offered", "offset", "opened", "operated", "optimized", "orchestrated", "ordered", "organized", "oriented", "originated", "outlined", "overcame", "overhauled", "oversaw",
        "packaged", "painted", "participated", "partnered", "patented", "perceived", "performed", "persuaded", "phased", "photographed", "piloted", "pinpointed", "pioneered", "placed", "planned", "played", "polled", "popularized", "positioned", "predicted", "prepared", "prescribed", "presented", "preserved", "presided", "prevented", "printed", "prioritized", "probed", "processed", "procured", "produced", "profiled", "programmed", "projected", "promoted", "proofread", "proposed", "protected", "proved", "provided", "publicized", "published", "pulled", "purchased", "pursued",
        "qualified", "quantified", "queried", "questioned", "quoted",
        "raised", "rallied", "ran", "ranked", "rated", "reached", "read", "realigned", "rebuilt", "received", "recognized", "recommended", "reconciled", "reconstructed", "recorded", "recovered", "recruited", "rectified", "redesigned", "reduced", "reengineered", "referred", "refined", "refocused", "reformed", "regulated", "rehabilitated", "reinforced", "reinstated", "related", "relayed", "released", "relieved", "remediated", "remodeled", "rendered", "renegotiated", "renovated", "reorganized", "repaired", "replaced", "replenished", "replicated", "reported", "represented", "reprogrammed", "researched", "reshaped", "resolved", "responded", "restored", "restructured", "resulted", "retained", "retooled", "retrieved", "revamped", "reversed", "reviewed", "revised", "revitalized", "rewarded", "routed", "ran",
        "safeguarded", "salvaged", "saved", "scanned", "scheduled", "schemed", "screened", "scripted", "scrutinized", "sculpted", "searched", "secured", "segmented", "selected", "separated", "sequenced", "served", "serviced", "set", "settled", "shaped", "shared", "sharpened", "shipped", "shortened", "showcased", "shrank", "simplified", "simulated", "sketched", "sold", "solidified", "solved", "sorted", "sought", "sparked", "spearheaded", "specialized", "specified", "speculated", "spoke", "sponsored", "stabilized", "staffed", "staged", "standardized", "started", "steered", "stimulated", "stopped", "strategized", "streamlined", "strengthened", "stressed", "stretched", "structured", "studied", "submitted", "substituted", "succeeded", "suggested", "summarized", "superseded", "supervised", "supplied", "supported", "surpassed", "surveyed", "sustained", "symbolized", "synchronized", "synthesized", "systematized",
        "tabulated", "tackled", "tailored", "targeted", "taught", "teamed", "terminated", "tested", "testified", "tightened", "timed", "traced", "tracked", "traded", "trained", "transacted", "transcribed", "transferred", "transformed", "translated", "transmitted", "transported", "traveled", "treated", "trimmed", "tripled", "troubleshot", "tutored", "typed",
        "uncovered", "underlined", "understood", "undertook", "underwrote", "unearthed", "unified", "united", "unraveled", "updated", "upgraded", "upheld", "utilized",
        "vacated", "validated", "valued", "verbalized", "verified", "viewed", "vindicated", "visited", "visualized", "voiced", "volunteered", "voted",
        "waived", "walked", "weighed", "welcomed", "widened", "witnessed", "won", "worked", "wrote",
        "yielded", "zoned"
    ]
    action_verb_count = 0
    verbs_found = set()
    for token in doc:
        if token.pos_ == "VERB" and token.lemma_.lower() in action_verbs_list:
            action_verb_count += 1
            verbs_found.add(token.lemma_.lower())

    if action_verb_count < 10:
         feedback.append(f"Suggestion: Found {action_verb_count} action verbs. Strong resumes often use many impactful action verbs (e.g., 15-25+) to start bullet points describing accomplishments.")
    elif action_verb_count < 20:
        feedback.append(f"Info: Found {action_verb_count} action verbs. Good start! Consider if more can be used to strengthen accomplishment statements.")
    else:
         feedback.append(f"Good: Detected {action_verb_count} action verbs. This helps make your accomplishments sound dynamic!")

    if verbs_found:
         feedback.append(f"Info: Some action verbs used: {', '.join(list(verbs_found)[:5])}{'...' if len(verbs_found) > 5 else ''}.")
    score_data = {'action_verb_count': action_verb_count}
    return feedback, score_data

def check_quantifiable_achievements(doc):
    feedback = []
    quantifiable_count = 0
    achievement_keywords = ["increased", "decreased", "achieved", "reduced", "grew", "improved", "optimized", "saved", "generated", "led to", "resulted in", "delivered", "completed", "exceeded", "streamlined"]
    for sent in doc.sents:
        has_number = any(token.like_num or token.text == "%" or token.text.lower() in ["$", "€", "£", "k", "m", "usd", "eur"] for token in sent)
        has_achievement_verb = any(token.lemma_.lower() in achievement_keywords for token in sent)
        if has_number and has_achievement_verb:
            quantifiable_count += 1
    if quantifiable_count == 0:
        feedback.append("Suggestion (High Priority): No clear quantifiable achievements found. Use numbers, percentages, or monetary values to demonstrate the impact of your work (e.g., 'Increased sales by 15%', 'Reduced costs by $10K', 'Managed a team of 5').")
    elif quantifiable_count < 3:
        feedback.append(f"Suggestion: Found {quantifiable_count} potential quantifiable achievement(s). Aim to include more to make your impact clear and measurable. Each key role should ideally have 1-2 quantifiable points.")
    else:
        feedback.append(f"Good: Detected {quantifiable_count} potential quantifiable achievements. This significantly strengthens your resume!")
    score_data = {'quantifiable_count': quantifiable_count}
    return feedback, score_data

def check_skills_section(text, doc):
    feedback = []
    text_lower = text.lower()
    skills_section_present = "skill" in text_lower or "proficiencies" in text_lower or "expertise" in text_lower or "technologies" in text_lower or "competencies" in text_lower
    if not skills_section_present:
        feedback.append("Suggestion: A dedicated 'Skills' section is highly recommended for listing technical and other key competencies. This makes it easy for recruiters to spot relevant abilities.")
    
    technical_skills_keywords = [
        "python", "java", "c++", "c#", "javascript", "typescript", "html", "css", "scss", "sass", "php", "ruby", "go", "swift", "kotlin", "rust", "scala",
        "sql", "mysql", "postgresql", "mongodb", "nosql", "sqlite", "oracle", "sql server", "cassandra", "redis",
        "react", "react.js", "angular", "angular.js", "vue", "vue.js", "next.js", "node.js", "express", "express.js", "django", "flask", "spring", "spring boot", ".net", "asp.net", "laravel", "ruby on rails",
        "aws", "azure", "gcp", "google cloud", "amazon web services", "docker", "kubernetes", "k8s", "terraform", "ansible", "jenkins", "gitlab ci", "ci/cd", "devops",
        "linux", "unix", "windows server", "macos", "bash", "powershell",
        "machine learning", "ml", "data analysis", "data science", "artificial intelligence", "ai", "deep learning", "natural language processing", "nlp",
        "pandas", "numpy", "scipy", "scikit-learn", "sklearn", "tensorflow", "keras", "pytorch", "matplotlib", "seaborn", "jupyter",
        "git", "github", "gitlab", "bitbucket", "jira", "confluence", "agile", "scrum", "kanban",
        "autocad", "solidworks", "revit", "matlab", "excel", "vba", "tableau", "power bi", "qlik", "sap", "oracle erp", "salesforce", "crm", "erp",
        "photoshop", "illustrator", "figma", "sketch", "adobe xd", "ui/ux",
        "cybersecurity", "penetration testing", "network security", "cryptography"
    ]
    found_tech_skills = set()
    for token in doc:
        if token.lemma_.lower() in technical_skills_keywords:
            found_tech_skills.add(token.lemma_.lower())
    for skill_phrase in [s for s in technical_skills_keywords if " " in s or "." in s or "#" in s]:
        if skill_phrase in text_lower:
                found_tech_skills.add(skill_phrase)
    
    found_tech_skills_count = len(found_tech_skills)

    if found_tech_skills_count > 0 :
        feedback.append(f"Good: Identified {found_tech_skills_count} potential technical skills. Example(s): {', '.join(list(found_tech_skills)[:3])}{'...' if found_tech_skills_count > 3 else ''}.")
        if found_tech_skills_count < 5:
            feedback.append("Suggestion: If you have more technical skills, ensure they are listed clearly. Aim for 5-15 relevant technical skills depending on your field and experience.")
    else:
        if skills_section_present:
             feedback.append("Suggestion: Your skills section seems to be present, but few common technical skills were detected. Ensure you list specific tools, programming languages, and technologies.")
        else:
            feedback.append("Suggestion: No common technical skills detected. If you have them, list them in your 'Skills' section or integrate them into your experience descriptions.")

    feedback.append("Info: Remember to also showcase soft skills (e.g., communication, teamwork, problem-solving, leadership) through your experience descriptions and summary, not just by listing them in a skills section.")
    score_data = {'skills_section_present': skills_section_present, 'tech_skills_count': found_tech_skills_count}
    return feedback, score_data

def perform_spell_check(text):
    feedback = []
    spell = SpellChecker()
    clean_text = re.sub(r'[^\w\s]', ' ', text) 
    clean_text = re.sub(r'\d+', '', clean_text)    
    words = clean_text.lower().split()
    words_to_check = [word for word in words if len(word) > 2 and not word.isupper()]
    misspelled = spell.unknown(words_to_check)
    common_tech_terms_or_acronyms = {
        "aws", "gcp", "api", "sdk", "cicd", "devops", "sql", "nosql", "html", "css", "json", "uiux", "erp", "crm",
        "saas", "paas", "iaas", "agile", "scrum", "kanban", "jira", "git", "github", "kubernetes", "k8s",
        "microservices", "blockchain", "fintech", "edtech", "healthtech", "iot", "arvr", "aiops", "mlops"
    } 
    misspelled_filtered = [word for word in misspelled if word not in common_tech_terms_or_acronyms and not any(char.isdigit() for char in word)]

    if len(misspelled_filtered) > 0:
        feedback.append(f"Warning (Spelling): Found {len(misspelled_filtered)} potential spelling errors. Please review. Examples: {', '.join(list(misspelled_filtered)[:5])}{'...' if len(misspelled_filtered) > 5 else ''}")
        feedback.append("Suggestion: Proofread carefully or use a spell checker (like Grammarly or Word's built-in checker). Common errors include typos or domain-specific terms not in a standard dictionary. Ensure consistency in capitalization of proper nouns and acronyms.")
    else:
        feedback.append("Good: No obvious spelling errors detected by the basic checker. Always good to double-check manually.")
    score_data = {'misspelled_count': len(misspelled_filtered)}
    return feedback, score_data

def check_readability(text):
    feedback = []
    flesch_score = 0
    try:
        flesch_score = textstat.flesch_reading_ease(text)
        feedback.append(f"Info (Readability): Flesch Reading Ease score: {flesch_score:.2f} (Higher is better; 60-70 is generally good for wide audiences).")
        if flesch_score < 30:
            feedback.append("Suggestion: Readability is very low (college graduate level or higher). Try to simplify complex sentences, break up long paragraphs, and use more common vocabulary unless highly technical language is standard for your target roles.")
        elif flesch_score < 60:
            feedback.append("Suggestion: Readability is fairly difficult. Consider simplifying some sentences or jargon for broader understanding, especially if applying to roles outside of a highly specialized field.")
        else:
            feedback.append("Good: Readability score suggests the text is understandable for a general business audience.")

        grade_level = textstat.flesch_kincaid_grade(text)
        feedback.append(f"Info (Readability): Flesch-Kincaid Grade Level: {grade_level:.1f}. Aim for a grade level around 8-12 for general business communication, unless a higher level is specific to your field and target audience.")

    except Exception as e:
        feedback.append(f"Info: Could not calculate readability score. Error: {e}")
    score_data = {'flesch_score': flesch_score if 'flesch_score' in locals() and flesch_score != 0 else 50}
    return feedback, score_data

def check_use_of_i(text):
    feedback = []
    i_count = len(re.findall(r'\bI\b', text)) 
    i_contractions_count = len(re.findall(r"\b(I'm|I've|I'd|I’ll|I’d)\b", text, re.IGNORECASE))
    my_me_count = len(re.findall(r"\b(my|me)\b", text, re.IGNORECASE))
    total_first_person_count = i_count + i_contractions_count + my_me_count

    if total_first_person_count > 3: 
        feedback.append(f"Suggestion: Found first-person pronouns (I, my, me, I'm, etc.) used approximately {total_first_person_count} times. Resumes are typically written in an implied first-person (e.g., 'Managed a team' instead of 'I managed a team'). Consider rephrasing to be more professional and concise.")
    score_data = {'i_count': total_first_person_count}
    return feedback, score_data

def check_dates_format(text):
    feedback = []
    date_patterns = [
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b', 
        r'\b\d{1,2}\/\d{4}\b', 
        r'\b\d{1,2}\-\d{4}\b', 
        r'\b\d{4}\s*[-–—to]+\s*\d{4}\b', 
        r'\b\d{4}\s*[-–—to]+\s*(?:Present|Current|Ongoing|Till Date)\b', 
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\s*[-–—to]+\s*(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b', 
        r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\s*[-–—to]+\s*(?:Present|Current|Ongoing|Till Date)\b'
    ]
    dates_found_count = 0
    for pattern in date_patterns:
        dates_found_count += len(re.findall(pattern, text, re.IGNORECASE))

    if dates_found_count < 2: 
        feedback.append("Suggestion: Few standard date formats found for employment or education periods. Ensure your experience and education sections have clear and consistently formatted start and end dates (e.g., 'Month YYYY – Month YYYY' or 'Month YYYY – Present').")
    else:
        feedback.append(f"Info: Detected {dates_found_count} instances of common date formats. Consistency in formatting is key for readability.")
    score_data = {'dates_found_count': dates_found_count}
    return feedback, score_data


# --- Scoring Logic ---
# Using the more detailed scoring logic from your first definition
def calculate_resume_score(score_inputs):
    base_score = 100
    deductions = 0
    bonus_points = 0 

    if not score_inputs['contact_info']['email_found']: deductions += 10
    if not score_inputs['contact_info']['phone_found']: deductions += 10
    if not score_inputs['contact_info']['linkedin_found']: deductions += 3

    sections_ratio = score_inputs['sections']['required_sections_found'] / score_inputs['sections']['total_required_sections']
    if sections_ratio < 0.5: deductions += 15 
    elif sections_ratio < 0.75: deductions += 10 
    elif sections_ratio < 1.0: deductions += 5  
    else: bonus_points += 2 

    if not score_inputs['length']['length_ok']: deductions += 5
    wc = score_inputs['length']['word_count']
    if 400 <= wc <= 700 : bonus_points += 2

    av_count = score_inputs['action_verbs']['action_verb_count']
    if av_count < 5: deductions += 8
    elif av_count < 10: deductions += 5
    elif av_count < 15: deductions += 2
    elif av_count >= 20: bonus_points += 3 

    qa_count = score_inputs['quantifiable']['quantifiable_count']
    if qa_count == 0: deductions += 18
    elif qa_count < 2: deductions += 10
    elif qa_count < 4: deductions += 5
    elif qa_count >= 5: bonus_points += 5 

    if not score_inputs['skills']['skills_section_present']: deductions += 7
    elif score_inputs['skills']['tech_skills_count'] < 3: deductions += 4 
    elif score_inputs['skills']['tech_skills_count'] < 5: deductions += 2
    elif score_inputs['skills']['tech_skills_count'] >= 10: bonus_points += 2 

    misspelled = score_inputs['spelling']['misspelled_count']
    if misspelled > 5: deductions += 12
    elif misspelled > 2: deductions += 7
    elif misspelled > 0: deductions += 3

    f_score = score_inputs['readability']['flesch_score']
    if f_score < 30: deductions += 8
    elif f_score < 50: deductions += 5
    elif f_score < 60: deductions += 2
    elif f_score >= 70: bonus_points += 2 

    i_usage_count = score_inputs['use_of_i']['i_count'] 
    if i_usage_count > 5: deductions += 5
    elif i_usage_count > 2: deductions += 2

    if score_inputs['dates']['dates_found_count'] < 2: deductions += 4 
    elif score_inputs['dates']['dates_found_count'] < 4: deductions += 2 

    final_score = max(0, min(100, base_score - deductions + bonus_points)) 
    return int(final_score)


# --- Main Analysis Orchestrator ---
# Using the more detailed one from your first definition
def analyze_resume_content(text):
    feedback_results = []
    score_inputs = {} 

    if not text or not text.strip():
        feedback_results.append("Error: The extracted text is empty. Cannot analyze.")
        return feedback_results, 0 

    doc = nlp(text) 

    feedback_results.append("--- Overall & Contact ---")
    fb, data = check_contact_info(text)
    feedback_results.extend(fb); score_inputs['contact_info'] = data
    fb, data = check_resume_length(text)
    feedback_results.extend(fb); score_inputs['length'] = data

    feedback_results.append("\n--- Structure & Sections ---")
    fb, data = check_section_headings(text)
    feedback_results.extend(fb); score_inputs['sections'] = data
    fb, data = check_dates_format(text)
    feedback_results.extend(fb); score_inputs['dates'] = data

    feedback_results.append("\n--- Content & Impact ---")
    fb, data = check_action_verbs(doc)
    feedback_results.extend(fb); score_inputs['action_verbs'] = data
    fb, data = check_quantifiable_achievements(doc)
    feedback_results.extend(fb); score_inputs['quantifiable'] = data
    fb, data = check_skills_section(text, doc)
    feedback_results.extend(fb); score_inputs['skills'] = data

    feedback_results.append("\n--- Language & Professionalism ---")
    fb, data = perform_spell_check(text)
    feedback_results.extend(fb); score_inputs['spelling'] = data
    fb, data = check_readability(text)
    feedback_results.extend(fb); score_inputs['readability'] = data
    fb, data = check_use_of_i(text)
    feedback_results.extend(fb); score_inputs['use_of_i'] = data

    resume_score = calculate_resume_score(score_inputs)

    feedback_results.append(f"\n--- Overall Score: {resume_score}/100 ---")
    if resume_score >= 85:
        feedback_results.append("Excellent! Your resume hits most of the key marks for a strong document. It's likely to perform well with both ATS and human reviewers.")
    elif resume_score >= 70:
        feedback_results.append("Good foundation! Your resume has several strong points. Addressing the suggestions can elevate it further and increase its effectiveness.")
    elif resume_score >= 50:
        feedback_results.append("Needs improvement. Your resume has potential but requires attention to several key areas. Focus on the suggestions marked 'High Priority' or 'Warning'.")
    else:
        feedback_results.append("Significant improvement needed. Your resume may be missing critical elements or have issues that could hinder your job search. Systematically address the feedback provided.")

    feedback_results.append("\n--- General Advice ---")
    feedback_results.append("Info: This is an automated analysis. While it provides valuable insights, also consider having your resume reviewed by a career advisor, mentor, or trusted professional in your field.")
    feedback_results.append("Info: Tailor your resume for each specific job application. Highlight the skills and experiences most relevant to the job description, and try to incorporate keywords from it.")
    feedback_results.append("Info: Ensure your resume is free of grammatical errors (this tool has basic spell check, but grammar is more complex). Use tools like Grammarly or ask someone to proofread.")
    feedback_results.append("Info: Keep your formatting clean, consistent, and professional. Avoid using tables, columns, or unusual fonts that might confuse Applicant Tracking Systems (ATS).")

    return [f for f in feedback_results if f is not None], resume_score


# --- Flask Routes ---
@app.route('/', methods=['GET', 'POST'])
def render_index_page(): # Renamed from 'index' to avoid endpoint collision
    feedback_messages = []
    extracted_text_content = ""
    resume_score = None 

    if request.method == 'POST':
        if 'resume' not in request.files:
            feedback_messages.append("Error: No file part in the request.")
            # Pass now=datetime.now for consistency if your template uses it on GET
            return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score, now=datetime.now)

        file = request.files['resume']

        if file.filename == '':
            feedback_messages.append("Error: No file selected.")
            return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score, now=datetime.now)

        if file:
            filename = file.filename
            file_stream = io.BytesIO()
            file.save(file_stream) 
            file_stream.seek(0) 

            error_message = None
            if filename.lower().endswith('.pdf'):
                extracted_text_content, error_message = extract_text_from_pdf(file_stream)
            elif filename.lower().endswith('.docx'):
                extracted_text_content, error_message = extract_text_from_docx(file_stream)
            else:
                feedback_messages.append("Error: Unsupported file type. Please upload a PDF or DOCX file.")
                return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score, now=datetime.now)

            if error_message:
                feedback_messages.append(f"Error during text extraction: {error_message}")
            elif extracted_text_content and extracted_text_content.strip():
                feedback_messages.append(f"Info: Successfully extracted text from '{filename}' ({len(extracted_text_content)} characters).")
                analysis_results, resume_score_val = analyze_resume_content(extracted_text_content)
                feedback_messages.extend(analysis_results)
                resume_score = resume_score_val 
            else:
                feedback_messages.append("Warning: Could not extract any text from the file, or the file is empty. Please check the file content and format. If it's a scanned PDF, text extraction might fail.")
                resume_score = 0 

    return render_template('index.html',
                           feedback=feedback_messages,
                           text=extracted_text_content,
                           score=resume_score,
                           now=datetime.now)

# The '/analyze' route was defined in the second block of your original code.
# It seems to serve the same purpose as the POST to '/' but on a different URL.
# If it's intended to be different, keep it. If it's redundant, you might remove it or merge logic.
# For now, I'll assume it was part of the duplicated structure and might not be needed if '/' handles POST.
# If you need '/analyze', ensure its logic is what you expect. The version below is from your *second* block.
# If your POST logic is fully handled by render_index_page's POST block, you might not need this '/analyze' route.
# Let's keep it as it was in the second half of your code for now.
@app.route('/analyze', methods=['POST'])
def analyze():
    feedback_messages = []
    extracted_text_content = ""
    resume_score = None 

    # This is essentially the same as the POST block in render_index_page
    # Consider if this route is still needed or if functionality can be consolidated
    if 'resume' not in request.files:
        feedback_messages.append("Error: No file part in the request.")
        # Note: this render_template call in your original /analyze didn't pass `now`
        return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score)

    file = request.files['resume']

    if file.filename == '':
        feedback_messages.append("Error: No file selected.")
        return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score)

    if file:
        filename = file.filename
        # The original /analyze route read the file directly, not save to BytesIO then read.
        # For consistency with the main route, using BytesIO:
        file_stream = io.BytesIO()
        file.save(file_stream)
        file_stream.seek(0)

        error_message = None
        if filename.lower().endswith('.pdf'): # Used .endswith in original /analyze
            extracted_text_content, error_message = extract_text_from_pdf(file_stream)
        elif filename.lower().endswith('.docx'): # Used .endswith in original /analyze
            extracted_text_content, error_message = extract_text_from_docx(file_stream)
        else:
            feedback_messages.append("Error: Unsupported file type. Please upload a PDF or DOCX file.")
            return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score)

        if error_message:
            feedback_messages.append(f"Error during text extraction: {error_message}")
        elif extracted_text_content and extracted_text_content.strip():
            feedback_messages.append(f"Info: Successfully extracted text from '{filename}' ({len(extracted_text_content)} characters).")
            analysis_results, resume_score_val = analyze_resume_content(extracted_text_content)
            feedback_messages.extend(analysis_results)
            resume_score = resume_score_val
        else:
            feedback_messages.append("Warning: Could not extract any text from the file, or the file is empty.")
            resume_score = 0 

    return render_template('index.html', feedback=feedback_messages, text=extracted_text_content, score=resume_score)


if __name__ == '__main__':
    # For development, debug=True is fine. 
    # For production (like on Render), Gunicorn will be used and this block isn't run by Gunicorn.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)