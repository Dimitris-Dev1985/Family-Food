from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, get_flashed_messages
import sqlite3, unicodedata, random, re, json, traceback, os, openai, logging
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from datetime import datetime, timedelta
from jinja2 import pass_context
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_mail import Mail, Message
from fuzzywuzzy import process
from stopwords_gr import RAW_STOPWORDS


log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)


app = Flask(__name__)
app.secret_key = "d7gAq2d9bJz@7qK2kLxw!"

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'dpap.ee@gmail.com'
app.config['MAIL_PASSWORD'] = 'ednvljshnmwajhus'
mail = Mail(app)

DB = "family_food_app.db"

WEEKDAYS_GR = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
COOKING_METHODS = ['Φούρνος','Κατσαρόλα','Χύτρα','Τηγάνι','Σχάρα','Air-fryer']
#MAIN_CATEGORIES = ['Κόκκινο κρέας', 'Ψάρι', 'Όσπρια', 'Λαδερά', 'Ζυμαρικά', 'Πουλερικά', 'Σαλάτα']
MAIN_INGREDIENTS = []
# Mapping: Εμφανιζόμενο όνομα σεφ ➔ όνομα αρχείου avatar
CHEF_AVATAR_MAP = {
    'Άκης Πετρετζίκης': 'akis_petretzikis.jpg',
    'Αργυρώ Μπαρμπαρίγου': 'argyro_barbarigou.jpg',
    'Βασίλης Καλλίδης': 'vasilis_kallidis.jpg',
    'Ντίνα Νικολάου': 'ntina_nikolaou.jpg',
    'Γιάννης Λουκάκος': 'giannis_loukakos.jpg',
    'Στέλιος Παρλιάρος': 'stelios_parliaros.jpg',
    'Ελένη Ψυχούλη': 'eleni_psychouli.jpg',
    'Παναγιώτης Παπαγάλος': 'panagiotis_papagalos.jpg',
    'Λευτέρης Λαζάρου': 'lefteris_lazarou.jpg',
    'Μαίρη Παναγάκου': 'mairi_panagakou.jpg',
    'Άλλος Σεφ': 'default.jpg',  # Για άγνωστο/placeholder
}
known_ingredients = [
    "κοτόπουλο", "μοσχάρι", "χοιρινό", "αρνί", "ψάρι", "γαρίδες", "καλαμάρι", "χταπόδι", "μπακαλιάρος",
    "κεφτεδάκια", "λουκάνικο", "μπέικον", "ζαμπόν", "αυγό", "ασπράδι αυγού", "κρόκος αυγού",
    "πατάτες", "γλυκοπατάτα", "καρότο", "κρεμμύδι", "κρεμμύδι ξερό", "κρεμμυδάκι φρέσκο", "σκόρδο",
    "πράσο", "σελινόριζα", "σέλινο", "μαϊντανός", "άνηθος", "δυόσμος", "βασιλικός", "ρίγανη",
    "θυμάρι", "δεντρολίβανο", "φασκόμηλο", "δάφνη", "λεμόνι", "πορτοκάλι", "μανταρίνι", "μήλο",
    "αχλάδι", "μπανάνα", "ροδάκινο", "κεράσι", "φράουλα", "ανανάς", "αβοκάντο",
    "τομάτα", "ντοματίνια", "πιπεριά", "πιπεριά κόκκινη", "πιπεριά πράσινη", "πιπεριά κίτρινη", "πιπεριά Φλωρίνης",
    "μελιτζάνα", "κολοκύθι", "κολοκυθάκι", "μπρόκολο", "κουνουπίδι", "λάχανο", "μαρούλι", "σπανάκι", "χόρτα",
    "μανιτάρια", "μανιτάρι πλευρώτους", "μανιτάρι λευκό", "μανιτάρι πορτομπέλο",
    "φασόλια", "φάβα", "ρεβίθια", "φακές", "μπιζέλια", "κουκιά", "ροβίτσα",
    "ρύζι", "καρολίνα", "γλασέ", "ρύζι μπασμάτι", "κριθαράκι", "τραχανάς", "πλιγούρι", "πλιγουράκι", "ζυμαρικά", "σπαγγέτι", "πέννες", "μακαρόνια", "βίδες", "χυλοπίτες",
    "ελαιόλαδο", "ηλιέλαιο", "βούτυρο", "μαργαρίνη", "τυρί φέτα", "γραβιέρα", "ανθότυρο", "κεφαλοτύρι", "κασέρι", "μανούρι", "μυζήθρα", "ροκφόρ",
    "γιαούρτι", "γιαούρτι στραγγιστό", "κρέμα γάλακτος", "γάλα", "εβαπορέ", "ζαχαρούχο γάλα", "τυρί κρέμα", "παρμεζάνα", "μοτσαρέλα",
    "αλεύρι", "σιμιγδάλι", "ψωμί", "φρυγανιά", "φρυγανιά τριμμένη", "κουάκερ", "νιφάδες βρώμης", "μπισκότα", "ζάχαρη", "μέλι", "μελάσα", "σιρόπι αγαύης",
    "ξύδι", "ξύδι βαλσάμικο", "κρασί", "λευκό κρασί", "κόκκινο κρασί", "ούζο", "τσίπουρο", "κονιάκ",
    "αλάτι", "πιπέρι", "πιπέρι μαύρο", "πιπέρι κόκκινο", "πιπέρι πράσινο", "πιπέρι λευκό", "σουσάμι", "μαγιά", "μπέικιν πάουντερ", "σόδα",
    "κανέλα", "γαρύφαλλο", "μοσχοκάρυδο", "μπαχάρι", "κύμινο", "κόλιανδρος", "πάπρικα", "πιπέρι καγιέν", "πάστα ελιάς", "ελιά", "ελιά Καλαμών",
    "κακάο", "σοκολάτα", "κουβερτούρα", "σταγόνες σοκολάτας", "ταχίνι", "φιστικοβούτυρο", "ξηροί καρποί", "αμύγδαλο", "καρύδι", "φουντούκι", "φιστίκι", "κάστανο",
    "ζελατίνη", "ζελατίνη σε φύλλα", "σκόνη βανίλιας", "εκχύλισμα βανίλιας", "μαστίχα", "καραμέλα", "ζάχαρη άχνη", "ζάχαρη καστανή",
    "ζωμός", "ζωμός κότας", "ζωμός λαχανικών", "ζωμός μοσχαριού", "ζωμός ψαριού", "ζωμός κοτόπουλου",
    "τοματοπελτές", "πελτές τομάτας", "ντοματοχυμός", "χυμός λεμονιού", "χυμός πορτοκαλιού",
    "σταφίδες", "δάκρυα σοκολάτας", "μαρμελάδα", "γλυκό του κουταλιού", "λουκούμι", "σιρόπι", "κουβερτούρα", "σαλέπι",
    "παγωτό", "μπουτί αρνιού", "φιλέτο κοτόπουλου", "παϊδάκια", "σνίτσελ", "μπριζόλα", "ψαρονέφρι", "συκώτι", "γύρος", "κεμπάπ",
    "τσουρέκι", "κουλούρι", "κέικ", "παντεσπάνι", "μπακλαβάς", "γλυκά του ταψιού", "μελομακάρονα", "κουραμπιέδες", "καρυδόπιτα", "πορτοκαλόπιτα",
    "σούπα", "κρέμα", "πουρές", "μακαρονάδα", "λαζάνια", "μουσακάς", "γεμιστά", "παπουτσάκια", "ντολμαδάκια", "λαδερά", "λαχανικά", "σαλάτα", "αφρόψαρα", "αμπελόφυλλα", "μαραθόριζα",
    ]


default_minutes = 60

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

import requests

# Δημιουργούμε custom requests session που παρακάμπτει το SSL verification
req_session = requests.Session()
req_session.verify = False  # ⚠️ απενεργοποίηση SSL validation

# Το περνάμε στον OpenAI client
openai.requestssession = req_session

def get_db_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_user():    
    user_id = session.get("user_id")
#    if not user_id:
#        user_id = 1  # fallback μόνο για debug
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    members = conn.execute("SELECT * FROM family_members WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return user, members

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

def normalize(text):
    if text is None:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(c) != "Mn"
    ).lower().strip()
                                                                                                         
def build_system_prompt():
    """Χτίζει το system prompt με βάση τα διαθέσιμα ingredients"""
    return (
        "You are a helpful kitchen assistant that helps tired parents decide what to cook.\n"
        "Always reply in Greek, with a warm and casual tone.\n"

        "Your ONLY task is to manage and update these 6 fields:\n"
        "- max_time (integer minutes) - είναι ο χρόνος που έχει στη διάθεσή του ο χρήστης για μαγείρεμα (απαραίτητο να υπάρχει πάντα).\n"
        "- dish_category (string) - είναι κατηγορία στην οποία ανήκει μια συνταγή (e.g όσπρια, λαδερά, ζυμαρικά, ψάρι, κτλ). Δεν είναι απαραίτητο να υπάρχει πάντα, αλλά αν δοθεί από τον χρήστη πρέπει να καταγραφεί.\n"
        "- main_ingredient (string) - είναι το βασικό υλικό που θέλει να χρησιμοποιήσει ο χρήστης. Θα το βρείτε ΜΑΖΙ.\n"
        "- aux_ingredients (array) - είναι τα επιπλέον βοηθητικά υλικά που θέλει ο χρήστης να έχει η συνταγή (προσθέσεις ή αφαιρέσεις).\n"
        "- cooking_method (array) - είναι λίστα προκαθορισμένων μεθόδων μαγειρέματος που μπορεί να χρειαστεί να επεξεργαστείς (προσθέσεις ή αφαιρέσεις).\n"
        "- excluded_keywords (array) - είναι λίστα με λέξεις που μπορεί να χρειαστεί να επεξεργαστείς (προσθέσεις ή αφαιρέσεις).\n\n"

        "VERY IMPORTANT:\n"
        "• Your exclusive goal is to understand the user's cooking preferences and update (add or remove values) from the abovementioned fields, throught store_filters function_call.\n\n"
        "• ALWAYS respect the current state and update ONLY if the user changes something.\n"
        "• The function_call must include ALL fields that are relevant after each user message.\n"
        "• If asked a question by the user, ALWAYS provide an answer, even if you don't know what exactly asked.\n"
        "• The free_text ('content') is ONLY for a short, friendly confirmation message in Greek, use it ONLY if user asked something or if you didn't manage to update any field.\n"
        "• Never try to put JSON or structured data inside 'content', perform a function_call instead. \n\n"
        
        "Rules to respect when processing the user's message:\n"                    
        "1. If BOTH max_time AND main_ingredient are present after processing the message → DO NOT ask extra follow-up questions.\n"
        "2. If main_ingredient is missing at first, but found in user message → DO NOT ask again. Only ask if it’s still missing after processing.\n"
        "3. Along with main_ingredient, user may provide extra info regarding materials or cooking methods, e.g. say 'μοσχαρι κοκκινιστό'. You should analyze the user message in greek and extract the main and aux ingedient,\n"
            "in the above example → main_ingredient = 'μοσχαρι' and aux_ingredients = 'ντομάτα'.\n"
        "4. Aux_ingredients, cooking_method and excluded_keywords are optional refinements. If missing, DO NOT force the user to provide them.\n"
        "5. User may provide information about two or more fields in the same phrase, either with positive or negative contribution. You must extract ALL referred fields. (e.g. 'κοτόπουλο με πατάτες στο φούρνο χωρίς καρότα' \n"
            "→ main_ingredient = 'κοτόπουλο', aux_ingredients = 'πατάτες', cooking_method = 'Φούρνος', excluded_keywords = 'καρότα').\n"
        "6. If user rejects a material (π.χ. 'όχι ψάρι', 'δεν έχω καρότα', 'χωρίς κιμά') → remove it (if present) from aux_ingredients AND main_ingredient, AND add it to excluded_keywords.\n"
        "7. If the user explicitly mentions a material as main ingredient (e.g. 'σε ψάρι', 'κοτόπουλο', 'μοσχάρι με πατάτες'), you MUST ADD it as main_ingredient AND (if present) REMOVE from excluded_keywords.\n"
        "8. If user decides that finally has a material available that was previously missing → REMOVE from excluded_keywords AND add it to either main_ingredients OR aux_ingredient.\n"           
        "9. If the user explicitly mentions a cooking method (π.χ. 'στο φούρνο', 'σε σχάρα', 'με air fryer'), you MUST always include it in cooking_method.\n"
        "10. If the user explicitly says he wants to AVOID a cooking method (π.χ. 'όχι φούρνο', 'χωρίς τηγάνι', 'δεν θέλω σχάρα'), you must REMOVE that method from cooking_method.\n"
        "11. If aux_ingredients, cooking_method or excluded_keywords is not clearly updated, don't include them in your answer.\n"
        "12. Regarding time:\n"
            "- If the user specifies an *absolute time* → take it literally (π.χ. 'μισή ώρα'=30, 'μιάμιση ώρα'=90).\n"
            "- If the user speaks about *relative time* compared to the existing (π.χ. 'πιο γρήγορο', 'πιο αργά', 'συντομότερο'), do NOT invent arbitrary numbers, but adjust the current max_time value by up to ±20%.\n"
            "(e.g. if current time = 200 and user says 'πιο γρήγορο' → new time = 160 (20% less).\n"
        "13. Regarding dish_category: If found in user message, usually main_ingredient will be missing. Ask for it, don't assume main_ingeredient to be the same as dish_category.\n"
    )

def lookup_ingredient(raw):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT core FROM normalized_ingredients WHERE raw = ?', (raw,))
    row = c.fetchone()
    if row:
        # Αύξησε το times_used κατά 1
        c.execute('UPDATE normalized_ingredients SET times_used = times_used + 1 WHERE raw = ?', (raw,))
        conn.commit()
    conn.close()
    return row[0] if row else None

def cache_ingredient(raw, core):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT OR IGNORE INTO normalized_ingredients (raw, core, created_at, times_used) VALUES (?, ?, ?, 1)', (raw, core, now))
    # Αν υπάρχει ήδη, ενημέρωσε core και times_used
    c.execute('UPDATE normalized_ingredients SET core = ?, times_used = times_used + 1 WHERE raw = ?', (core, raw))
    conn.commit()
    conn.close()

def ai_normalize_ingredient(raw):
    prompt = (
    "Δώσε μου μόνο το βασικό ουσιαστικό ή τη βασική φράση (σε ονομαστική ενικού ή πληθυντικού όπως είναι φυσικό στην ελληνική), "
    "που αντιπροσωπεύει το κύριο υλικό ή συστατικό, από την παρακάτω φράση που συναντάται σε λίστα συνταγών. "
    "Αγνόησε επίθετα, επιρρήματα, διαστάσεις, ποσότητες, σημειώσεις, παρασκευαστικές οδηγίες, και όλα τα περιττά χαρακτηριστικά. "
    "Αν το κύριο υλικό αποτελείται από δύο λέξεις (π.χ. \"ζωμός κότας\", \"κρέμα γάλακτος\", \"ελαιόλαδο\"), κράτησε και τις δύο λέξεις. "
    "Απάντησε μόνο με την πλήρη, ορθογραφημένη λέξη ή φράση, όπως θα τη χρησιμοποιούσες σε ελληνικό λεξικό. "
    "Μην κόβεις γράμματα ή συλλαβές από το τέλος της λέξης. Μην αφήνεις λέξη ημιτελή. "
    "Ποτέ μην επιστρέφεις μόνο μέρος της λέξης (όπως \"κρεμμυδ\" αντί για \"κρεμμύδι\"). "
    "Δώσε μόνο τη λέξη ή τη φράση, χωρίς εισαγωγικά, εξηγήσεις ή επιπλέον χαρακτήρες.\n"
    f"Φράση: {raw}\n"
    )
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Είσαι ένας βοηθός που βρίσκει το βασικό υλικό σε λίστες υλικών συνταγών."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=8,
        temperature=0.0
    )
    return response['choices'][0]['message']['content'].strip()

def fix_ai_ingredient(ai_result, known_ingredients):
    # Αν το AI core υπάρχει ήδη στο λεξικό, το γυρνάς όπως είναι
    if ai_result in known_ingredients:
        return ai_result
    # Fuzzy-match: βρίσκει το πιο κοντινό string στο λεξικό σου
    best_match, score = process.extractOne(ai_result, known_ingredients)
    # Αν είναι πολύ κοντά (>85%), γύρνα το best match
    if score >= 85:
        return best_match
    # Αν όχι, γύρνα το AI core (έστω και αν είναι κομμένο)
    return ai_result

def fmt_ts(ts):
    # Μετατρέπει '2025-09-19T19:21:16.162959' σε '2025-09-19 19:21'
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ts or ""

def strip_tonos(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

def check_onboarding(user_id):
    conn = sqlite3.connect(DB)
    row = conn.execute("SELECT completed FROM onboarding_progress WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row and row[0]:
        return True
    return False

@app.route('/api/normalize_ingredient', methods=['POST'])
def normalize_ingredient_route():
    data = request.get_json()
    raw = data.get('text', '').strip()
    if not raw:
        return jsonify({'error': 'missing input'}), 400

    core = lookup_ingredient(raw)
    if not core:
        # 1. Πάρε το core από AI
        ai_core = ai_normalize_ingredient(raw)
        # 2. Κάνε "διόρθωση" με fuzzy match
        fixed_core = fix_ai_ingredient(ai_core, known_ingredients)
        # 3. Cache το corrected result στη βάση
        cache_ingredient(raw, fixed_core)
        core = fixed_core
    return jsonify({'core': core})



# ----------- START -----------
@app.route("/")
def index():
    if "user_id" in session:
        user_id = session["user_id"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        row = c.execute("SELECT completed FROM onboarding_progress WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        onboarding_done = row and row[0]

        if onboarding_done:
            return redirect(url_for("main"))
        else:
            # Redirect στην πρώτη ενδιάμεση σελίδα
            return redirect(url_for("onboarding_diet"))
    else:
        return redirect(url_for("welcome"))

@app.route("/onboarding_diet", methods=["GET", "POST"])
def onboarding_diet():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    diet = None

    if request.method == "POST":
        diet = request.form.get("diet", "")
        # Αποθήκευσε στο users table
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET diet=? WHERE id=?", (diet, user_id))
        conn.commit()
        conn.close()
        # Προχώρα στο επόμενο βήμα
        return redirect(url_for("onboarding_allergies"))

    # GET: φέρε τρέχουσα τιμή (αν υπάρχει)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    row = c.execute("SELECT diet FROM users WHERE id=?", (user_id,)).fetchone()
    if row:
        diet = row[0]
    conn.close()

    return render_template("onboarding_diet.html", diet=diet)

@app.route("/onboarding_allergies", methods=["GET", "POST"])
def onboarding_allergies():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    allergies = []

    if request.method == "POST":
        allergies_str = request.form.get("allergies", "")
        allergies = [a.strip() for a in allergies_str.split(",") if a.strip()]
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET allergies=? WHERE id=?", (",".join(allergies), user_id))
        conn.commit()
        conn.close()
        return redirect(url_for("onboarding_methods"))  # ή το επόμενο βήμα σου

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    row = c.execute("SELECT allergies FROM users WHERE id=?", (user_id,)).fetchone()
    if row and row[0]:
        allergies = [a.strip() for a in row[0].split(",") if a.strip()]
    conn.close()

    return render_template("onboarding_allergies.html", allergies=allergies)

@app.route("/onboarding_methods", methods=["GET", "POST"])
def onboarding_methods():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cooking_methods = []

    if request.method == "POST":
        methods_str = request.form.get("cooking_methods", "")
        cooking_methods = [m.strip() for m in methods_str.split(",") if m.strip()]
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("UPDATE users SET cooking_method=? WHERE id=?", (",".join(cooking_methods), user_id))
        # Ολοκλήρωση onboarding (π.χ. flag completed)
        c.execute("INSERT OR REPLACE INTO onboarding_progress (user_id, completed) VALUES (?, 1)", (user_id,))
        conn.commit()
        conn.close()
        return redirect(url_for("main"))  # ή όπου θες να πηγαίνει μετά

    # GET: φέρε τις υπάρχουσες μεθόδους αν υπάρχουν
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    row = c.execute("SELECT cooking_method FROM users WHERE id=?", (user_id,)).fetchone()
    if row and row[0]:
        cooking_methods = [m.strip() for m in row[0].split(",") if m.strip()]
    conn.close()

    return render_template("onboarding_methods.html", cooking_methods=cooking_methods)


# ----------- APP PAGES -----------

@app.route("/welcome")
def welcome():
    hour = datetime.now().hour
    greeting = "Καλημέρα" if hour < 12 else "Καλησπέρα"
    day_idx = datetime.now().weekday()  # 0 = Δευτέρα
    day_name = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"][day_idx]
    return render_template(
        "welcome.html",
        greeting=greeting,
        day_name=day_name
    )

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        first_name = request.form.get("first_name", "").strip()

        if not email or not password:
            flash("Email και κωδικός είναι υποχρεωτικά!", "danger")
            return redirect(url_for("signup"))

        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        existing = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash("Υπάρχει ήδη χρήστης με αυτό το email!", "warning")
            conn.close()
            return redirect(url_for("signup"))

        # Κωδικοποίηση κωδικού
        hashed_password = generate_password_hash(password)

        # Προσθήκη νέου χρήστη
        conn.execute("""
            INSERT INTO users (email, password, first_name)
            VALUES (?, ?, ?)
        """, (email, hashed_password, first_name))
        conn.commit()

        # Ανάκτηση του νέου id
        user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        conn.close()

        session["user_id"] = user_id
        session['signup_success'] = True
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if not get_flashed_messages() and not session.get("signup_success"):
            session.clear()
        return render_template("login.html")

    if request.method == "POST":
        action = request.form.get("action")
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row

        # ✅ Debug login bypass
        if action == "debug":
            user = conn.execute("SELECT * FROM users ORDER BY id LIMIT 1").fetchone()
            conn.close()
            if user:
                session["user_id"] = user["id"]
                # === ΝΕΟ: Ελεγχος για onboarding ===
                onboarding = check_onboarding(user["id"])
                if onboarding:
                    return redirect(url_for("main"))
                else:
                    return redirect(url_for("onboarding_diet"))
            else:
                flash("Δεν βρέθηκε χρήστης για debug login!", "danger")
                return redirect(url_for("login"))

        # ✅ Κανονικό login
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        # 1. Βρες τον χρήστη με βάση το email
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if not user:
            flash("Δεν υπάρχει χρήστης με αυτό το email.", "danger")
            return redirect(url_for("login"))

        # 2. Έλεγχος κωδικού (hashed)
        stored_hash = user["password"]  # ή "password_hash" αν το πεδίο λέγεται αλλιώς
        if check_password_hash(stored_hash, password):
            session["user_id"] = user["id"]
            session['login_success'] = True
            # === ΝΕΟ: Ελεγχος για onboarding ===
            onboarding = check_onboarding(user["id"])
            if onboarding:
                return redirect(url_for("main"))
            else:
                return redirect(url_for("onboarding_diet"))
        else:
            flash("Λανθασμένος κωδικός!", "danger")
            print("λαθος κωδικος")
            return redirect(url_for("login"))

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user:
            s = URLSafeTimedSerializer(app.secret_key)
            token = s.dumps(user["email"], salt='password-reset')
            reset_link = url_for('reset_password', token=token, _external=True)

            msg = Message(
                subject="Επαναφορά Κωδικού – Family Food",
                sender=("Family Food", app.config['MAIL_USERNAME']),
                recipients=[email]
            )
            msg.body = f"Για να επαναφέρεις τον κωδικό σου, κάνε κλικ στον παρακάτω σύνδεσμο:\n\n{reset_link}\n\nΑν δεν ζήτησες επαναφορά, αγνόησέ το."

            try:
                mail.send(msg)
                flash("✅ Σου στείλαμε email με οδηγίες επαναφοράς.", "success")
            except Exception:
                flash("❌ Σφάλμα κατά την αποστολή email. Δοκίμασε ξανά.", "danger")
        else:
            flash("⚠️ Δεν βρέθηκε λογαριασμός με αυτό το email.", "warning")

        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        s = URLSafeTimedSerializer(app.secret_key)
        email = s.loads(token, salt='password-reset', max_age=7200)  # 2 ώρες
    except SignatureExpired:
        flash("⏰ Ο σύνδεσμος έληξε. Ζήτησε νέο από τη σελίδα επαναφοράς.", "danger")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("❌ Μη έγκυρος σύνδεσμος επαναφοράς.", "danger")
        return redirect(url_for("forgot_password"))

    # Αναζητάμε τον χρήστη στη βάση
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user:
        flash("Ο λογαριασμός δεν βρέθηκε.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        pwd1 = request.form.get("password", "").strip()
        pwd2 = request.form.get("password2", "").strip()

        if len(pwd1) < 6:
            flash("Ο κωδικός πρέπει να έχει τουλάχιστον 6 χαρακτήρες.", "danger")
            return render_template("reset_password.html")

        if pwd1 != pwd2:
            flash("Οι κωδικοί δεν ταιριάζουν.", "danger")
            return render_template("reset_password.html")

        hash = generate_password_hash(pwd1)

        # Ενημέρωση κωδικού στη βάση
        conn = sqlite3.connect(DB)
        conn.execute("UPDATE users SET password = ? WHERE email = ?", (hash, email))
        conn.commit()
        conn.close()

        flash("✅ Ο κωδικός άλλαξε! Μπορείς να συνδεθείς τώρα.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

@app.route("/main")
@login_required
def main():
    clear_suggestions()
    
    user, _ = get_user()
    user_id = user["id"]

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row 
    
    # Διάβασε τα recipe_ids των αγαπημένων
    favs = conn.execute("SELECT recipe_id FROM favorite_recipes WHERE user_id=?", (user_id,)).fetchall()
    favorite_recipe_ids = [row[0] for row in favs]

    # Διάβασε το cooking_method του χρήστη
    user_row = conn.execute("SELECT cooking_method FROM users WHERE id=?", (user_id,)).fetchone()
    cooking_method = user_row["cooking_method"] if user_row else ""
        
    # Σπάσε τα σε λίστα (αν θες λίστα)
    cooking_methods = [m.strip() for m in cooking_method.split(",")] if cooking_method else []    
    
    conn.close()
    
    
    return render_template(
        "main.html",
        favorite_recipe_ids=favorite_recipe_ids,
        cooking_methods=cooking_methods
    )

@app.route('/recipe_page/<int:recipe_id>')
@login_required
def recipe_page(recipe_id):
    user_id = session.get('user_id', 0)
    user_name = None
    user_avatar = None
    
    print("\n========== /recipe_page CALLED ==========")
    print("[INPUT] recipe_id:", recipe_id)
    
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    recipe = conn.execute("""
        SELECT id, title,
               COALESCE(description,'') as description,
               COALESCE(servings,4) as servings,
               COALESCE(url,'') as url,
               COALESCE(chef,'') as chef,
               COALESCE(prep_time,0) as prep_time,
               COALESCE(cook_time,0) as cook_time,
               COALESCE(total_time,0) as total_time,
               COALESCE(method,'') as method,
               COALESCE(dish_category,'') as dish_category,
               COALESCE(ingredients,'') as ingredients,
               COALESCE(dish_tags,'') as dish_tags,
               COALESCE(instructions,'') as instructions,
               COALESCE(image_path,'') as image_path
        FROM recipes
        WHERE id = ?
    """, (recipe_id,)).fetchone()

    if not recipe:
        return "Recipe not found", 404

    # Υλικά
    ingredients = [line.strip() for line in recipe['ingredients'].splitlines() if line.strip()]
   
    # dish_tags
    dish_tags = [line.strip() for line in recipe['dish_tags'].splitlines() if line.strip()]
    
   
    # Οδηγίες
    instructions = [line.strip() for line in recipe['instructions'].splitlines() if line.strip()]
    
    # Εικόνα από static folder
    image_path = recipe['image_path'] if 'image_path' in recipe.keys() else ''
    
    if image_path and image_path.strip() != '':
        image_url = url_for('static', filename=f"images/recipes/{image_path}")
    else:
        image_url = url_for('static', filename="images/placeholder.jpg")

    # ========== ΕΛΕΓΧΟΣ FAVORITE ==========
    is_favorite = False
    if user_id:
        fav_row = conn.execute(
            "SELECT 1 FROM favorite_recipes WHERE user_id = ? AND recipe_id = ?",
            (user_id, recipe_id)
        ).fetchone()
        is_favorite = fav_row is not None

    user_row = conn.execute("SELECT servings FROM users WHERE id=?", (user_id,)).fetchone()
    servings = user_row["servings"] if user_row and "servings" in user_row.keys() else None


    conn.close()

    if user_id:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute('SELECT first_name FROM users WHERE id = ?', (user_id,))
        row = c.fetchone()
        if row and row['first_name']:
            user_name = row['first_name']
        else:
            user_name = 'Χρήστης'
        user_avatar = f'/static/images/avatars/{user_id}.jpg'
        conn.close()
    else:
        user_name = 'Επισκέπτης'
        user_avatar = '/static/images/avatars/default.jpg'

    avatar_filename = CHEF_AVATAR_MAP.get(recipe['chef'], 'default.jpg')


    return render_template(
        'recipe_page.html',
        recipe=recipe,
        ingredients=ingredients,
        instructions=instructions,
        dish_tags=dish_tags,
        image_url=image_url,
        is_favorite=is_favorite,
        user_id=user_id,
        user_name=user_name,
        user_avatar=user_avatar,
        servings=servings,
        chef_avatar=avatar_filename
    )

@app.route("/profile")
@login_required
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # --- User Info ---
    cur.execute("SELECT first_name FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        return "User not found", 404
    first_name = row[0]
    avatar_path = f"/static/images/avatars/{user_id}.jpg"

    # --- User Stats ---
    cur.execute("SELECT COUNT(*) FROM favorite_recipes WHERE user_id = ?", (user_id,))
    favorites_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM cooked_dishes WHERE user_id = ?", (user_id,))
    cooked_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM recipe_ratings WHERE user_id = ?", (user_id,))
    ratings_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM recipe_comments WHERE user_id = ?", (user_id,))
    comments_count = cur.fetchone()[0]

    # --- Αγαπημένα ---
    
    
    def get_chef_avatar(chef_name):
        filename = CHEF_AVATAR_MAP.get(chef_name, 'default.jpg')
        return f"/static/images/avatars/{filename}"
        
    cur.execute("""
    SELECT r.id, r.title, r.image_path, r.chef, r.total_time, r.main_ingredient, r.method
    FROM favorite_recipes f
    JOIN recipes r ON f.recipe_id = r.id
    WHERE f.user_id = ?
    ORDER BY f.id DESC
    """, (user_id,))
    favorites = []
    for row in cur.fetchall():
        chef_avatar = get_chef_avatar(row[3])  # row[3] είναι το r.chef
        favorites.append({
            "id": row[0],
            "title": row[1],
            "image": row[2],
            "chef_name": row[3],
            "chef_avatar": chef_avatar,
            "total_time": row[4],
            "main_ingredient": row[5],
            "method": row[6]
        })


    # --- Είδες πρόσφατα (last seen) ---
    cur.execute("""
        SELECT r.id, r.title, r.image_path, r.chef, r.total_time, lsr.seen_at, r.main_ingredient, r.method
        FROM last_seen_recipes lsr
        JOIN recipes r ON lsr.recipe_id = r.id
        WHERE lsr.user_id = ?
        ORDER BY lsr.seen_at DESC
    """, (user_id,))
    last_seen = []
    for row in cur.fetchall():
        chef_avatar = get_chef_avatar(row[3])
        last_seen.append({
            "id": row[0],
            "title": row[1],
            "image": row[2],
            "chef_name": row[3],
            "chef_avatar": chef_avatar,
            "total_time": row[4],
            "seen_at": row[5],
            "main_ingredient": row[6],
            "method": row[7]
        })

    # --- Δραστηριότητα (comments, ratings, cooked) --- 
    
    # Comments
    cur.execute("""
        SELECT rc.id as comment_id, rc.recipe_id, r.title, r.image_path, r.total_time, r.chef, rc.created_at, 'comment' as type, rc.comment, NULL as rating
        FROM recipe_comments rc
        JOIN recipes r ON rc.recipe_id = r.id
        WHERE rc.user_id = ?
    """, (user_id,))
    comments = [
        {
            "comment_id": row[0],            # <-- ΝΕΟ!
            "recipe_id": row[1],
            "recipe_title": row[2],
            "image_url": row[3],
            "total_time": row[4],
            "chef_name": row[5],
            "chef_avatar": get_chef_avatar(row[5]),
            "timestamp": fmt_ts(row[6]),
            "type": row[7],
            "comment": row[8],
            "rating": None
        }
        for row in cur.fetchall()
    ]

    # Ratings
    cur.execute("""
        SELECT rr.id as rating_id, rr.recipe_id, r.title, r.image_path, r.total_time, r.chef, rr.updated_at, 'rating' as type, NULL as comment, rr.rating
        FROM recipe_ratings rr
        JOIN recipes r ON rr.recipe_id = r.id
        WHERE rr.user_id = ?
    """, (user_id,))
    ratings = [
        {
            "rating_id": row[0],             # <-- ΝΕΟ!
            "recipe_id": row[1],
            "recipe_title": row[2],
            "image_url": row[3],
            "total_time": row[4],
            "chef_name": row[5],
            "chef_avatar": get_chef_avatar(row[5]),
            "timestamp": row[6],
            "type": row[7],
            "comment": None,
            "rating": row[9]
        }
        for row in cur.fetchall()
    ]

    # Cooked
    cur.execute("""
        SELECT cd.id as cooked_id, cd.recipe_id, r.title, r.image_path, r.total_time, r.chef, cd.cooked_at, 'cooked' as type, cd.notes, NULL as rating
        FROM cooked_dishes cd
        JOIN recipes r ON cd.recipe_id = r.id
        WHERE cd.user_id = ?
    """, (user_id,))

    cooked_activity = [
        {
            "cooked_id": row[0],                
            "recipe_id": row[1],
            "recipe_title": row[2],
            "image_url": row[3],
            "total_time": row[4],
            "chef_name": row[5],
            "chef_avatar": get_chef_avatar(row[5]),
            "timestamp": row[6],
            "type": row[7],
            "notes": row[8],
            "comment": None,
            "rating": None
        }
        for row in cur.fetchall()
    ]



    # Ταξινόμηση όλης της activity κατά timestamp (πιο πρόσφατα πρώτα)
    activity = comments + ratings + cooked_activity
    activity.sort(key=lambda x: x['timestamp'], reverse=True)

    # --- Render σελίδας με Jinja2 ---
    return render_template(
        "profile.html",
        user_id=user_id,
        avatar_path=avatar_path,
        first_name=first_name,
        stats={
            "favorites": favorites_count,
            "cooked": cooked_count,
            "ratings": ratings_count,
            "comments": comments_count
        },
        favorites=favorites,
        last_seen=last_seen,
        activity=activity
    )

@app.route('/edit_profile', methods=["GET", "POST"])
@login_required
def edit_profile():
    # Βεβαιώσου ότι ο χρήστης είναι log-in
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        diet = request.form.get("diet", "").strip()
        allergies = request.form.get("allergies", "")
        cooking_methods = request.form.get("cooking_methods", "")
        servings = request.form.get("servings", "")

        allergies_list = [x.strip() for x in allergies.split(",") if x.strip()]
        cooking_methods_list = [x.strip() for x in cooking_methods.split(",") if x.strip()]
        servings = int(servings) if servings and servings.isdigit() else 4

        # ------ Avatar upload χωρίς καμία ενημέρωση στη βάση ------
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename:
            filename = f"{user_id}.jpg"
            save_path = os.path.join(app.root_path, "static", "images", "avatars", filename)
            avatar_file.save(save_path)
            # ΔΕΝ αλλάζεις τίποτα στη βάση!

        conn.execute("""
            UPDATE users
            SET first_name = ?,
                email = ?,
                diet = ?,
                allergies = ?,
                cooking_method = ?,
                servings = ?
            WHERE id = ?
        """, (
            name,
            email,
            diet,
            ",".join(allergies_list),
            ",".join(cooking_methods_list),
            servings,
            user_id
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("profile"))


    # GET: Φόρτωσε τα στοιχεία του user από τη βάση!
    user = conn.execute("""
        SELECT first_name, email, diet, allergies, cooking_method, servings
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    # Πέρνα τις λίστες αλλεργιών/μεθόδων ως python λίστα για το template
    user_dict = dict(user)
    user_dict["allergies"] = [x.strip() for x in (user["allergies"] or "").split(",") if x.strip()]
    user_dict["cooking_method"] = [x.strip() for x in (user["cooking_method"] or "").split(",") if x.strip()]

    # Προσαρμόζεις το path avatar εδώ αν θες...
    user_dict["avatar"] = "/static/images/avatars/%s.jpg" % user_id

    print(user_dict)

    conn.close()
    return render_template("edit_profile.html", user=user_dict, avatar_path=user_dict["avatar"])



# ----------- RATINGS για recipe -----------

@app.route('/api/rate_recipe', methods=['POST'])
def rate_recipe():
    data = request.json
    recipe_id = data.get('recipe_id')
    user_id = data.get('user_id')
    rating = data.get('rating')
    if not recipe_id or not user_id or not rating:
        return jsonify({'success': False, 'error': 'missing fields'}), 400
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id FROM recipe_ratings WHERE recipe_id = ? AND user_id = ?", (recipe_id, user_id))
    row = c.fetchone()
    if row:
        c.execute("UPDATE recipe_ratings SET rating = ?, updated_at = CURRENT_TIMESTAMP WHERE recipe_id = ? AND user_id = ?", (rating, recipe_id, user_id))
    else:
        c.execute("INSERT INTO recipe_ratings (recipe_id, user_id, rating) VALUES (?, ?, ?)", (recipe_id, user_id, rating))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/get_recipe_avg_rating')
def get_recipe_avg_rating():
    recipe_id = request.args.get('recipe_id')
    if not recipe_id:
        return jsonify({'success': False, 'error': 'missing recipe_id'}), 400
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT AVG(rating), COUNT(*) FROM recipe_ratings WHERE recipe_id = ?", (recipe_id,))
    avg_rating, count = c.fetchone()
    conn.close()
    return jsonify({'success': True, 'avg_rating': avg_rating, 'count': count})

@app.route('/api/get_recipe_rating')
def get_recipe_rating():
    recipe_id = request.args.get('recipe_id')
    user_id = request.args.get('user_id')
    if not recipe_id or not user_id:
        return jsonify({'success': False, 'error': 'missing fields'}), 400
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT rating FROM recipe_ratings WHERE recipe_id = ? AND user_id = ?", (recipe_id, user_id))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'success': True, 'rating': row[0]})
    else:
        return jsonify({'success': True, 'rating': None})

@app.route('/api/recipe_ratings/<int:rating_id>', methods=['DELETE'])
def delete_recipe_rating(rating_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    try:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute('SELECT user_id FROM recipe_ratings WHERE id = ?', (rating_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
        if str(row['user_id']) != str(user_id):
            conn.close()
            return jsonify({'error': 'Δεν έχεις δικαίωμα διαγραφής'}), 403

        c.execute('DELETE FROM recipe_ratings WHERE id = ?', (rating_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print('[ERROR] delete_recipe_rating:', e)
        return jsonify({'error': 'DB error'}), 500


# ----------- COMMENTS για recipe -----------

@app.route('/api/recipe_comments')
def get_recipe_comments():
    recipe_id = request.args.get('recipe_id')
    if not recipe_id:
        return jsonify({'error': 'Missing recipe_id'}), 400
    try:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute('''
            SELECT c.*, u.first_name as username,
                   '/static/images/avatars/' || c.user_id || '.jpg' as avatar_url
            FROM recipe_comments c
            LEFT JOIN users u ON c.user_id = u.id
            WHERE c.recipe_id = ?
            ORDER BY c.created_at DESC
        ''', (recipe_id,))
        rows = c.fetchall()
        comments = [dict(row) for row in rows]
        conn.close()
        return jsonify({'comments': comments})
    except Exception as e:
        print('[ERROR] get_recipe_comments:', e)
        return jsonify({'error': 'DB error'}), 500

@app.route('/api/recipe_comments', methods=['POST'])
def add_recipe_comment():
    data = request.json
    recipe_id = data.get('recipe_id')
    user_id = data.get('user_id')
    comment = data.get('comment', '').strip()

    if not (recipe_id and user_id and comment):
        return jsonify({'error': 'Missing data'}), 400
    if len(comment) < 2 or len(comment) > 1000:
        return jsonify({'error': 'Το σχόλιο πρέπει να έχει 2-1000 χαρακτήρες.'}), 400

    try:
        now = datetime.utcnow().isoformat()
        conn = get_db_conn()
        c = conn.cursor()
        c.execute('''
            INSERT INTO recipe_comments (recipe_id, user_id, comment, created_at)
            VALUES (?, ?, ?, ?)
        ''', (recipe_id, user_id, comment, now))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return jsonify({'ok': True, 'id': new_id, 'created_at': now})
    except Exception as e:
        print('[ERROR] add_recipe_comment:', e)
        return jsonify({'error': 'DB error'}), 500

@app.route('/api/recipe_comments/<int:comment_id>', methods=['DELETE'])
def delete_recipe_comment(comment_id):
    user_id = request.args.get('user_id')  # Πρέπει να περάσει το frontend τον user_id
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    try:
        conn = get_db_conn()
        c = conn.cursor()
        # Πρώτα τσέκαρε αν ο user είναι ο owner του comment (ή αν είναι admin, μπορείς να προσθέσεις έλεγχο)
        c.execute('SELECT user_id FROM recipe_comments WHERE id = ?', (comment_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
        if str(row['user_id']) != str(user_id):
            conn.close()
            return jsonify({'error': 'Δεν έχεις δικαίωμα διαγραφής'}), 403

        c.execute('DELETE FROM recipe_comments WHERE id = ?', (comment_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print('[ERROR] delete_recipe_comment:', e)
        return jsonify({'error': 'DB error'}), 500


# ----------- COOCKED DISHES -----------

@app.route('/api/cooked_dishes/<int:cooked_id>', methods=['DELETE'])
def delete_cooked_dish(cooked_id):
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({'error': 'Missing user_id'}), 400

    try:
        conn = get_db_conn()
        c = conn.cursor()
        c.execute('SELECT user_id FROM cooked_dishes WHERE id = ?', (cooked_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'Not found'}), 404
        if str(row['user_id']) != str(user_id):
            conn.close()
            return jsonify({'error': 'Δεν έχεις δικαίωμα διαγραφής'}), 403

        c.execute('DELETE FROM cooked_dishes WHERE id = ?', (cooked_id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        print('[ERROR] delete_cooked_dish:', e)
        return jsonify({'error': 'DB error'}), 500

@app.route('/api/cooked_notes/<int:cooked_id>', methods=['PATCH'])
def update_cooked_note(cooked_id):
    data = request.json
    user_id = data.get('user_id')
    note = data.get('note', '').strip()
    # Μπορείς να βάλεις εδώ επιπλέον validation αν θες

    if not user_id or not note:
        return jsonify({'success': False, 'error': 'missing fields'}), 400

    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        # Επιβεβαίωση ότι το cooked_dishes ανήκει στον χρήστη
        c.execute("SELECT id FROM cooked_dishes WHERE id = ? AND user_id = ?", (cooked_id, user_id))
        row = c.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'not found'}), 404

        c.execute("UPDATE cooked_dishes SET notes = ?, cooked_at = CURRENT_TIMESTAMP WHERE id = ?", (note, cooked_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        print('[ERROR] update_cooked_note:', e)
        return jsonify({'success': False, 'error': 'DB error'}), 500


# ----------- LAST SEEN DISHES -----------
@app.route("/api/mark_recipe_seen", methods=["POST"])
def mark_recipe_seen():
    user, _ = get_user()
    if not user:
        return {"success": False, "error": "Unauthorized"}, 401

    data = request.get_json()
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return {"success": False, "error": "Missing recipe_id"}, 400

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Προσπάθεια για UPSERT (αν υπάρχει το ενημερώνει, αλλιώς το προσθέτει)
    conn.execute("""
        INSERT INTO last_seen_recipes (user_id, recipe_id, seen_at)
        VALUES (?, ?, datetime('now', 'localtime'))
        ON CONFLICT(user_id, recipe_id) DO UPDATE SET seen_at=datetime('now', 'localtime')
    """, (user["id"], recipe_id))
    conn.commit()
    conn.close()
    return {"success": True}


# ----------- SIMILAR DISHES -----------
@app.route('/api/similar')
def api_similar():
    recipe_id = request.args.get("recipe_id", type=int)
    max_time = request.args.get("max_time", type=int) # π.χ. 120

    if not recipe_id or not max_time:
        return {"success": False, "error": "Missing recipe_id or max_time"}, 400

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    base_row = conn.execute("""
        SELECT main_ingredient FROM recipes WHERE id = ?
    """, (recipe_id,)).fetchone()

    if not base_row or not base_row["main_ingredient"]:
        print("[DEBUG] Δεν βρέθηκε main_ingredient για το recipe_id:", recipe_id)
        return {"success": False, "error": "No main_ingredient for this recipe"}, 404

    main_ingredient = base_row["main_ingredient"].strip().lower()
#    print("[DEBUG] main_ingredient (normalized):", main_ingredient)

    sql = """
        SELECT id, title, chef, COALESCE(image_path, '') as image_path, total_time
        FROM recipes
        WHERE id != ?
          AND (
            LOWER(ingredients) LIKE ?
            OR LOWER(title) LIKE ?
            OR LOWER(main_ingredient) LIKE ?
          )
          AND total_time IS NOT NULL AND total_time != ''
    """
    param = f'%{main_ingredient}%'
    params = (recipe_id, param, param, param)

    similar = conn.execute(sql, params).fetchall()

    recipes = []
    for row in similar:
        try:
            tt = int(row["total_time"])
        except Exception:
            continue
        recipes.append({
            "id": row["id"],
            "title": row["title"],
            "chef": row["chef"],
            "total_time": tt,
            "image_path": row["image_path"]
        })

    close = []
    others = []
    for r in recipes:
        if abs(r["total_time"] - max_time) <= 20:
            close.append(r)
        else:
            others.append(r)
    close = sorted(close, key=lambda r: abs(r["total_time"] - max_time))
    others = sorted(others, key=lambda r: abs(r["total_time"] - max_time))

    top = close[:6]
    if len(top) < 6:
        top += others[:(6-len(top))]

    data = []
    for row in top:
        if row["image_path"] and row["image_path"].strip() != "":
            image_url = url_for('static', filename=f'images/recipes/{row["image_path"]}')
        else:
            image_url = url_for('static', filename='images/placeholder.jpg')
        chef = row["chef"]
        avatar_file = CHEF_AVATAR_MAP.get(chef, "default.jpg")
        chef_avatar = url_for('static', filename='images/avatars/' + avatar_file)
        data.append({
            "id": row["id"],
            "title": row["title"],
            "chef": row["chef"],
            "total_time": row["total_time"],
            "image_url": image_url,
            "chef_avatar": chef_avatar
        })

#    print("[DEBUG] /api/similar ->", data)
    return {"success": True, "recipes": data}




# 🔹 Global variables
COOKING_METHODS = ['Φούρνος','Κατσαρόλα','Χύτρα','Τηγάνι','Σχάρα','Air-fryer']
NORMALIZED_METHODS = { normalize(m): m for m in COOKING_METHODS }
SYSTEM_PROMPT = build_system_prompt()

@app.route("/test_openai")
def test_openai():

    try:
        # Μπορείς να δηλώσεις το API key εδώ αν δεν το έχεις βάλει αλλού:
        # openai.api_key = "your-openai-api-key"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": "Πόσο κάνουν 2 + 2;"
            }],
            temperature=0
        )

        reply = response.choices[0].message["content"].strip()
        return f"<h3>✅ Επιτυχής σύνδεση με OpenAI!</h3><p><b>AI απάντηση:</b> {reply}</p>"

    except Exception as e:
        traceback_str = traceback.format_exc()
        return f"<h3>❌ Σφάλμα κατά τη σύνδεση με OpenAI</h3><pre>{traceback_str}</pre>"

@app.route("/ai_reply_test")
def ai_reply_test():
    print("[DEBUG] 🧪 Serving ai_reply_test.html")
    return render_template("ai_reply_test.html")

@app.route("/test_ai")
def test_ai():
    return render_template("test_ai.html")


@app.route('/api/dish_categories')
def get_dish_categories():
    import sqlite3
    categories = set()
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute('SELECT dish_category FROM recipes WHERE dish_category IS NOT NULL AND dish_category != ""')
        rows = c.fetchall()
        for row in rows:
            for cat in str(row[0]).split(','):
                cleaned = cat.strip()
                if cleaned:
                    categories.add(cleaned)
        conn.close()
        sorted_cats = sorted(categories, key=lambda x: x.lower())
        return jsonify({'categories': sorted_cats})
    except Exception as e:
        print('[ERROR] get_dish_categories:', e)
        return jsonify({'categories': []}), 500

@app.route("/get_main_tags")
def get_main_tags():
    category = request.args.get("category")
    print("[DEBUG] 🔍 GET /get_main_tags called with category =", category)

    if not category:
        print("[WARN] ❗ No category provided in request.args")
        print("[DEBUG] ➡️ Returning: {'tags': []} (400)")
        return jsonify({"tags": []}), 400

    conn = None
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        print("[DEBUG] 📋 Running SQL for main tags with category LIKE %{}%".format(category))
        c.execute("""
            SELECT DISTINCT main_ingredient
            FROM recipes
            WHERE dish_category LIKE ?
              AND main_ingredient IS NOT NULL
              AND main_ingredient != ''
        """, (f"%{category}%",))
        rows = c.fetchall()
        print(f"[DEBUG] 📥 Raw SQL rows:", rows)
        tags = sorted(set(r[0].strip() for r in rows if r[0] and r[0].strip()))
        print(f"[DEBUG] ✅ Cleaned tags list:", tags)
        print(f"[DEBUG] ➡️ Returning: {{'tags': {tags}}} (200)")
        return jsonify({"tags": tags})
    except Exception as e:
        print("[ERROR] ❌ Exception while fetching main tags:", repr(e))
        print("[DEBUG] ➡️ Returning: {'tags': []} (500)")
        return jsonify({"tags": []}), 500
    finally:
        if conn:
            conn.close()


@app.route("/ai_reply", methods=["POST"])
def ai_reply_v3():


    def coerce_int(val):
        try:
            if val is None: return None
            if isinstance(val, (int, float)): return int(val)
            s = str(val).strip()
            if s == "" or s.lower() == "null": return None
            return int(float(s))
        except:
            return None

    def parse_absolute_minutes(text_norm):
        if not text_norm:
            return None
        m = re.search(r"(\d+)\s*λεπ", text_norm)
        if m: return int(m.group(1))
        m = re.search(r"(\d+)\s*ωρ", text_norm)
        if m: return int(m.group(1)) * 60
        if "μισ" in text_norm and "ωρ" in text_norm:
            return 30
        return None

    def clamp_relative_time(old_minutes, new_minutes, abs_time_present, rel_phrase_present):
        if not old_minutes or not new_minutes:
            return new_minutes
        if abs_time_present:
            return new_minutes
        if rel_phrase_present:
            low = int(round(old_minutes * 0.8))
            high = int(round(old_minutes * 1.2))
            clamped = max(low, min(high, new_minutes))
            if clamped != new_minutes:
                print(f"[RULE] ⏱️ Clamped relative time from {new_minutes} to {clamped} (range {low}-{high})")
            return clamped
        return new_minutes

    def is_affirmative(msg: str) -> bool:
        m = normalize(msg)
        if m.startswith("οκ") or m.startswith("ok") or m.startswith("ναι") or m.startswith("συμφων"):
            return True
        if "ενταξει" in m:
            return True
        return False

    try:
        print("\n========== /ai_reply CALLED ==========")
        data = request.get_json() or {}
        print("[INPUT] Raw:", data)

        message = str(data.get("message") or "").strip()
        current_max_time = coerce_int(data.get("max_time"))
        current_main_ingredient = data.get("main_ingredient")
        current_cooking_method = data.get("preferred_methods") or []
        excluded_keywords = data.get("excluded") or []
        aux_ingredients = data.get("aux_ingredients") or []
        current_dish_category = data.get("dish_category") or None

        print(f"[STATE] max_time={current_max_time}, ingredient={current_main_ingredient}, method={current_cooking_method}, excluded={excluded_keywords}, aux={aux_ingredients}, category={current_dish_category}")
        if not message:
            return jsonify({"error": "Empty message"}), 400

        msg_norm = normalize(message)
        system_prompt = SYSTEM_PROMPT
        user_context = f"Current state:\n- max_time: {current_max_time}\n- main_ingredient: {current_main_ingredient}\n- cooking_method: {current_cooking_method}\n- excluded_keywords: {excluded_keywords}\n- aux_ingredients: {aux_ingredients}\n- dish_category: {current_dish_category}\n"

        ai_response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context + "\nUser: " + message}
            ],
            functions=[{
                "name": "store_filters",
                "description": "Extracts user's food preferences",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "main_ingredient": {"type": "string"},
                        "max_time": {"type": "integer"},
                        "cooking_method": {"type": "array", "items": {"type": "string"}},
                        "excluded_keywords": {"type": "array", "items": {"type": "string"}},
                        "aux_ingredients": {"type": "array", "items": {"type": "string"}},
                        "dish_category": {"type": "string"}         # ΝΕΟ: dish_category
                    },
                    "required": []
                }
            }],
            function_call="auto"
        )

        ai_msg = ai_response.choices[0].message
        ai_free_text = (ai_msg.get("content") or "").strip()
        print("[AI] free_text:", ai_free_text)

        filters = {
            "max_time": current_max_time,
            "main_ingredient": current_main_ingredient,
            "cooking_method": current_cooking_method[:],
            "excluded_keywords": excluded_keywords[:],
            "aux_ingredients": aux_ingredients[:],
            "dish_category": current_dish_category             # ΝΕΟ: dish_category
        }

        # --- Αποθήκευση προτεινόμενου main_ingredient από free_text
        suggested_main = None
        for ingr in MAIN_INGREDIENTS:
            if normalize(ingr) in normalize(ai_free_text):
                suggested_main = ingr
                break
        if suggested_main:
            session["last_suggested_mainIng"] = suggested_main
            print(f"[SUGGEST] 💡 AI suggested main candidate: {suggested_main}")

        # --- Αν χρήστης απαντήσει affirmative και έχουμε candidate
        if is_affirmative(message):
            if session.get("last_suggested_mainIng"):
                filters["main_ingredient"] = session["last_suggested_mainIng"]
                print(f"[IMPLICIT] ✅ User accepted suggestion: {filters['main_ingredient']}")

        # ➖ Αν το AI είπε να αφαιρέσει κάτι από excluded
        for excluded in excluded_keywords[:]:
            if normalize(excluded) in normalize(ai_free_text) and "αφαιρ" in normalize(ai_free_text):
                filters["excluded_keywords"] = [x for x in filters["excluded_keywords"] if x != excluded]
                print(f"[EXCLUDE] ➖ Removed excluded ingredient: {excluded}")

        ai_fc_set_time = False
        ai_fc_set_category = False

        if ai_msg.get("function_call") and ai_msg["function_call"]["name"] == "store_filters":
            raw_args = ai_msg["function_call"].get("arguments", "{}")
            print("[AI] function_call args:", raw_args)
            try:
                parsed = json.loads(raw_args)

                if "max_time" in parsed and parsed["max_time"] is not None:
                    filters["max_time"] = parsed["max_time"]
                    ai_fc_set_time = True
                if "main_ingredient" in parsed and parsed["main_ingredient"]:
                    filters["main_ingredient"] = parsed["main_ingredient"]
                if "cooking_method" in parsed:
                    if parsed["cooking_method"]:
                        filters["cooking_method"] = parsed["cooking_method"]
                    else:
                        filters["cooking_method"] = current_cooking_method
                if "excluded_keywords" in parsed:
                    new_excluded = parsed["excluded_keywords"]
                    if new_excluded:
                        for word in new_excluded:
                            if word not in filters["excluded_keywords"]:
                                filters["excluded_keywords"].append(word)
                                print(f"[EXCLUDE] ➕ Added excluded: {word}")
                    removed_excludes = [x for x in excluded_keywords if x not in new_excluded]
                    if removed_excludes:
                        filters["excluded_keywords"] = [
                            x for x in filters["excluded_keywords"] if x not in removed_excludes
                        ]
                        for removed in removed_excludes:
                            print(f"[EXCLUDE] ➖ Removed (via function_call): {removed}")

                if "aux_ingredients" in parsed:
                    new_aux = parsed["aux_ingredients"]
                    if new_aux:
                        for ingr in new_aux:
                            if ingr not in filters["aux_ingredients"]:
                                filters["aux_ingredients"].append(ingr)
                                print(f"[AUX] ➕ Added aux ingredient: {ingr}")

                if "dish_category" in parsed and parsed["dish_category"]:
                    filters["dish_category"] = parsed["dish_category"]
                    ai_fc_set_category = True
                    print(f"[CATEGORY] ✅ AI set category: {filters['dish_category']}")

                print("[AI] parsed filters:", parsed)

            except Exception as e:
                print("[WARN] Failed to parse function_call args:", e)

        # --- Χειρισμός χρόνου (absolute / relative)
        abs_from_user = parse_absolute_minutes(msg_norm)
        abs_from_ai = parse_absolute_minutes(normalize(ai_free_text))
        abs_time_present = False

        if abs_from_ai is not None:
            filters["max_time"] = abs_from_ai
            abs_time_present = True

        faster = any(p in msg_norm for p in ["πιο γρηγορ","πιο συντομ","λιγοτερο χρονο"])
        slower = any(p in msg_norm for p in ["πιο αργ","περισσοτερ","μεγαλυτερο χρονο"])
        rel_phrase_present = faster or slower

        if ai_fc_set_time and current_max_time and not abs_time_present:
            original_ai_time = coerce_int(filters["max_time"])
            filters["max_time"] = clamp_relative_time(current_max_time, original_ai_time, False, rel_phrase_present)

        if not ai_fc_set_time and rel_phrase_present and current_max_time:
            target = int(round(current_max_time * 0.8)) if faster else int(round(current_max_time * 1.2))
            filters["max_time"] = clamp_relative_time(current_max_time, target, False, True)

        def apply_method_from(text_norm):
            found_negation = False
            for m in COOKING_METHODS:
                nm = normalize(m)
                if f"οχι {nm}" in text_norm or f"χωρις {nm}" in text_norm or f"δεν θελω {nm}" in text_norm:
                    remain = [x for x in filters["cooking_method"] if x != m]
                    filters["cooking_method"] = remain[:]
                    if nm not in filters["excluded_keywords"]:
                        filters["excluded_keywords"].append(nm)
                        print(f"[METHOD] ❌ Excluded method: {m}")
                    found_negation = True
            if found_negation:
                return
            best_match = process.extractOne(
                text_norm, list(NORMALIZED_METHODS.keys()), scorer=fuzz.partial_ratio
            )
            if best_match:
                matched_norm, score = best_match
                best_method = NORMALIZED_METHODS[matched_norm]
                print(f"[FUZZY] Matching method → '{best_method}' (score: {score})")
                if score >= 85:
                    filters["cooking_method"] = [best_method]
                    print(f"[FUZZY] ✅ Detected method: {best_method}")
                else:
                    print(f"[FUZZY] ⛔️ Ignored low-confidence or negated match")

        apply_method_from(msg_norm)
        apply_method_from(normalize(ai_free_text))

        # --- Fuzzy matcher για main (αν δεν υπάρχει ήδη)
        if not filters.get("main_ingredient"):
            result = process.extractOne(msg_norm, MAIN_INGREDIENTS, scorer=fuzz.partial_ratio)
            if result:
                best, score, _ = result
                ni = normalize(best)
                negation_phrases = [f"χωρις {ni}", f"οχι {ni}", f"δεν εχω {ni}", f"χωρις το {ni}"]
                is_negated = any(phrase in msg_norm for phrase in negation_phrases)
                if score > 80 and not is_negated and best not in filters["excluded_keywords"]:
                    filters["main_ingredient"] = best
                    print(f"[MAIN] ✅ Detected main ingredient: {best}")
                elif is_negated:
                    print(f"[FUZZY] 🚫 Ignored '{best}' as main because found in negation context")

        # --- Εντοπισμός excluded
        for msg in [msg_norm, normalize(ai_free_text)]:
            for ingr in MAIN_INGREDIENTS:
                ni = normalize(ingr)
                if (
                    f"χωρις {ni}" in msg
                    or f"οχι {ni}" in msg
                    or f"δεν εχω {ni}" in msg
                    or f"χωρις το {ni}" in msg
                ):
                    if ingr not in filters["excluded_keywords"]:
                        filters["excluded_keywords"].append(ingr)
                        print(f"[EXCLUDE] ➕ Excluded ingredient: {ingr}")

        # --- Always cooking_method as list
        if isinstance(filters.get("cooking_method"), str):
            filters["cooking_method"] = [m.strip() for m in filters["cooking_method"].split(",") if m.strip()]

        logout = False
        if "terminate_session" in normalize(ai_free_text):
            logout = True
            ai_free_text = "Δεν μπορώ να συνεχίσω τη συζήτηση. Καλή συνέχεια."

        # --- Cleanup conflicts
        if filters.get("main_ingredient"):
            if filters["main_ingredient"] in filters["excluded_keywords"]:
                print(f"[CLEANUP] 🚫 Conflict: '{filters['main_ingredient']}' is both main and excluded.")
                if filters["main_ingredient"] != current_main_ingredient:
                    filters["main_ingredient"] = current_main_ingredient
                    print(f"[CLEANUP] 🔄 Restored main_ingredient back to '{current_main_ingredient}'")
                filters["excluded_keywords"] = [
                    x for x in filters["excluded_keywords"] if x != filters["main_ingredient"]
                ]
                print(f"[CLEANUP] 🧹 Removed '{filters['main_ingredient']}' from excluded_keywords")

        for ex in filters["excluded_keywords"]:
            if ex in filters["aux_ingredients"]:
                filters["aux_ingredients"].remove(ex)
                print(f"[CLEANUP] 🧹 Removed '{ex}' from aux_ingredients (was excluded)")

        filters["cooking_method"] = [
            m for m in filters["cooking_method"] if normalize(m) not in filters["excluded_keywords"]
        ]

        # --- Fuzzy matcher για dish_category (αν έχεις λίστα)
        if not filters.get("dish_category") and "DISH_CATEGORIES" in globals():
            result = process.extractOne(msg_norm, DISH_CATEGORIES, scorer=fuzz.partial_ratio)
            if result:
                best, score, _ = result
                ni = normalize(best)
                negation_phrases = [f"χωρις {ni}", f"οχι {ni}", f"δεν θελω {ni}", f"χωρις το {ni}"]
                is_negated = any(phrase in msg_norm for phrase in negation_phrases)
                if score > 80 and not is_negated:
                    filters["dish_category"] = best
                    print(f"[CATEGORY] ✅ Detected dish_category: {best}")
                elif is_negated:
                    print(f"[CATEGORY] 🚫 Ignored '{best}' as category because found in negation context")

        # --- Τελική απάντηση
        if not filters["main_ingredient"]:
            if ai_free_text:
                reply_text = ai_free_text
            else:
                reply_text = "Ποιο βασικό υλικό θα ήθελες να χρησιμοποιήσεις; 🙂"
        elif not filters["max_time"]:
            reply_text = "Πόσο χρόνο διαθέτεις για μαγείρεμα; 🙂"
        elif not filters["dish_category"]:
            reply_text = "Τι είδους πιάτο θέλεις; (π.χ. κυρίως, σαλάτα, συνοδευτικό)"
        else:
            changes = []
            if filters["max_time"] != current_max_time:
                changes.append(f"χρόνο {filters['max_time']} λεπτά")
            if filters["main_ingredient"] != current_main_ingredient:
                changes.append(f"υλικό {filters['main_ingredient']}")
            if (
                isinstance(filters["cooking_method"], list)
                and filters["cooking_method"] != current_cooking_method
                and filters["cooking_method"]
            ):
                changes.append(f"μέθοδο {', '.join(filters['cooking_method'])}")
            new_excluded = [x for x in filters["excluded_keywords"] if x not in excluded_keywords]
            if new_excluded:
                changes.append(f"χωρίς {', '.join(new_excluded)}")
            if filters["dish_category"] != current_dish_category and filters["dish_category"]:
                changes.append(f"είδος {filters['dish_category']}")
            reply_text = "Οκ, ενημέρωσα: " + ", ".join(changes) if changes else ai_free_text

        print("[OUTPUT] 🤖 Reply:", reply_text)
        print("[OUTPUT] 🎯 Filters:", filters)
        print("========== /ai_reply END ==========\n")

        return jsonify({"reply": reply_text, "filters": filters, "logout": logout})

    except Exception as e:
        print("[ERROR] ❌ Exception in ai_reply:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500



@app.route('/ai_suggest_dish', methods=['POST'])
def ai_suggest_dish():

    def normalize(text):
        if not text:
            return ""
        text = unicodedata.normalize("NFD", str(text))
        text = "".join(c for c in unicodedata.normalize("NFD", str(text)) if unicodedata.category(c) != "Mn")
        return text.lower()

    COOKING_WORDS = {
        "στη","στο","στον","στις","στην","χυτρα","ταχυτητας","φουρνο","τηγανι","σχαρα","airfryer","air","fryer","ρυζι","πατατες"
    }

    def preprocess_title(title):
        words = [w for w in normalize(title).split() if w not in COOKING_WORDS]
        return " ".join(words[:2])

    STOPWORDS_GR = { normalize(w) for w in RAW_STOPWORDS }

    def clean_message(msg):
        text = normalize(msg)
        print("[DEBUG] normalized message:", text)
        text = re.sub(r"[!?,.;]", " ", text)
        words = [w for w in text.split() if w not in STOPWORDS_GR and w not in COOKING_WORDS]
        return " ".join(words)

    # Helper για να προσθέτεις image_url
    def enrich_dish_with_image_url(d):
        image_path = ""
        if ("image_path" in d.keys()) and d["image_path"] and str(d["image_path"]).strip() != "":
            image_path = d["image_path"]
        image_url = url_for('static', filename=f"images/recipes/{image_path}") if image_path else url_for('static', filename="images/placeholder.jpg")
        result = dict(d)
        result["image_url"] = image_url
        return result

    suggestion_messages = [
        "Τέλεια, τι λες για τα παρακάτω πιάτα; Πάτα πάνω σε όποιο θες για να δεις λεπτομέρειες!",
        "Τέλεια, πως σου φαίνονται τα παρακάτω; Πάτα πάνω σε όποιο θες για λεπτομέρειες!",
        "Τέλεια, τι θα έλεγες για τα παρακάτω;  Πάτα πάνω σε όποιο θες για περισσότερες λεπτομέρειες!",
        "Τέλεια, ορίστε μερικές ιδέες, πάτα πάνω σε όποια κάρτα θες για να δεις τα υλικά:",
        "Τέλεια, ορίστε μερικά πιάτα που ταιριάζουν στις προτιμήσεις σου, πάτα πάνω σε όποιο θες για να δεις λεπτομέρειες:"
    ]

    try:
        print("\n========== /ai_suggest_dish CALLED ==========")
        data = request.get_json() or {}
        print("[INPUT] Raw:", data)
        step = data.get("step")
        user_message = clean_message(data.get("message", "") or "")
        print("[DEBUG] 🧹 Cleaned user input:", user_message)

        max_time = data.get("max_time")
        main_ingredient = data.get("main_ingredient")
        preferred_method = data.get("preferred_methods")
        excluded = data.get("excluded") or []
        if not isinstance(excluded, list):
            excluded = []
        preferred_chef = data.get("chef")

        print(f"[STATE] max_time={max_time}, ingredient={main_ingredient}, method={preferred_method}, excluded={excluded}, chef={preferred_chef}")

        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        conn.create_function("remove_tonos", 1, remove_tonos)

        already_suggested = session.get("suggested_dish_ids", [])
        final_dishes = []
        seen_ids = set()


        # =============== Branch 0: Quick category+main_ingredient lookup ==============
        if data.get("step") == 0:
            print("[DEBUG] ========== Branch 0 (step=0) ==========")
            dish_category = data.get("dish_category", "")
            main_ingredient = data.get("main_ingredient", "")
            excluded = data.get("excluded") or []
            if not isinstance(excluded, list):
                excluded = []
            allergens = data.get("allergens") or session.get("allergens") or []
            if not isinstance(allergens, list):
                allergens = []

            # ΝΕΟ: suggested_dish_ids
            already_suggested = session.get("suggested_dish_ids", [])
            q_base = """
            FROM recipes
            LEFT JOIN favorite_recipes fav 
                 ON fav.recipe_id = recipes.id AND fav.user_id = ?
            WHERE 1=1
            """
            params = [session.get("user_id")]

            if dish_category:
                q_base += " AND remove_tonos(LOWER(dish_category)) LIKE ?"
                params.append(f"%{remove_tonos(dish_category.lower())}%")
            if main_ingredient:
                q_base += " AND remove_tonos(LOWER(main_ingredient)) LIKE ?"
                params.append(f"%{remove_tonos(main_ingredient.lower())}%")

            if max_time:
                try:
                    q_base += " AND total_time <= ?"
                    params.append(int(max_time))
                except Exception as e:
                    print("[WARN] Invalid max_time (branch 0):", e)

            # Excluded ηδη προτεινόμενα!
            if already_suggested:
                placeholders = ",".join("?" * len(already_suggested))
                q_base += f" AND recipes.id NOT IN ({placeholders})"
                params.extend(already_suggested)

            for item in excluded:
                ex_norm = remove_tonos(str(item).lower())
                q_base += " AND remove_tonos(ingredients) NOT LIKE ?"
                params.append(f"%{ex_norm}%")
            for allergen in allergens:
                al_norm = remove_tonos(str(allergen).lower())
                q_base += " AND remove_tonos(ingredients) NOT LIKE ?"
                params.append(f"%{al_norm}%")

            count_query = "SELECT COUNT(*) " + q_base
            select_query = "SELECT recipes.*, CASE WHEN fav.recipe_id IS NOT NULL THEN 1 ELSE 0 END as is_favorite " + q_base + " ORDER BY is_favorite DESC, RANDOM() LIMIT 3"

            print("[SQL]", select_query)
            print("[PARAMS]", params)

            conn = sqlite3.connect(DB)
            conn.row_factory = sqlite3.Row
            conn.create_function("remove_tonos", 1, remove_tonos)

            count_res = conn.execute(count_query, params).fetchone()
            matches_count = count_res[0] if count_res else 0

            dishes = conn.execute(select_query, params).fetchall()
            conn.close()

            print(f"[DEBUG] 🍽️ Branch0 returned {len(dishes)} dishes (total matches: {matches_count}):", [d["title"] for d in dishes])

            results = []
            for d in dishes:
                rec = dict(d)
                image_path = rec.get("image_path") or rec.get("image_url")
                if image_path:
                    if not image_path.startswith("http"):
                        image_url = "/static/images/recipes/" + image_path.lstrip("/")
                    else:
                        image_url = image_path
                    rec["image_url"] = image_url
                else:
                    rec["image_url"] = "/static/images/recipes/default.jpg"

                # --- Chef Avatar --- 
                chef = rec.get("chef")
                avatar_file = CHEF_AVATAR_MAP.get(chef, "default.jpg")
                rec["chef_avatar"] = "/static/images/avatars/" + avatar_file

                results.append(rec)

            # Προσθήκη στα suggested (μόνο τα νέα)
            new_ids = [rec["id"] for rec in results if rec["id"] not in already_suggested]
            session["suggested_dish_ids"] = already_suggested + new_ids

            if not results:
                return jsonify({
                    "success": False,
                    "message": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια.. Θες να το ξαναπροσπαθήσουμε;; Πες μου με τι έχεις στο μυαλό σου για σήμερα! - 0",
                    "dishes": [],
                    "matches_count": matches_count
                })
            else:
                return jsonify({
                    "success": True,
                    "message": random.choice(suggestion_messages),
                    "dishes": results,
                    "matches_count": matches_count
                })


        # =============== Branch 1: lexical match ==================
        if user_message:
            print("[DEBUG] ========== Branch 1 ==========")
            sql = """
                SELECT recipes.*,
                CASE WHEN fav.recipe_id IS NOT NULL THEN 1 ELSE 0 END as is_favorite
                FROM recipes
                LEFT JOIN favorite_recipes fav
                ON fav.recipe_id = recipes.id AND fav.user_id = ?
                """
            
            print("[DEBUG] SQL Branch1:", sql)


            candidates = conn.execute(sql, (session.get("user_id"),)).fetchall()

            def normalize_token(s):
                return remove_tonos(s.strip().lower()) if s else ""

            user_tokens = [normalize_token(w) for w in user_message.split() if len(w.strip()) > 2]
            user_message_norm = normalize_token(user_message)
            print("[DEBUG] User tokens for title fuzzy:", user_tokens)
            print("[DEBUG] Normalized user_message:", user_message_norm)

            matches = []
            for idx, row in enumerate(candidates):
                rec = dict(row)
                rid = rec["id"]
                raw_title = rec.get("title", "") or ""
                main_ing = rec.get("main_ingredient", "") or ""
                ingredients = rec.get("ingredients", "") or ""
                fav_flag = rec["is_favorite"]

                raw_title_norm = normalize_token(raw_title)
                main_ing_norm = normalize_token(main_ing)
                ingredients_norm = normalize_token(ingredients)

                # Fuzzy per token στον τίτλο
                token_scores = [fuzz.token_set_ratio(token, raw_title_norm) for token in user_tokens]
                max_token_score = max(token_scores) if token_scores else 0
                mean_token_score = sum(token_scores) / len(token_scores) if token_scores else 0

                # Fuzzy σε main_ingredient
                score_main_ing = fuzz.token_set_ratio(user_message_norm, preprocess_title(main_ing_norm))

                # Ingredients: token in ingredients
                matched_tokens = [token for token in user_tokens if token in ingredients_norm]
                score_ingredient_like = len(matched_tokens) > 0

                # Θεώρησε match αν έστω ένα token στον τίτλο >= 80 ή μέσος όρος >= 70 ή fuzzy main_ing >= 80 ή βρέθηκε token στα ingredients
                is_title_match = max_token_score >= 80 or mean_token_score >= 70
                is_main_ing_match = score_main_ing >= 80

                
                
                if is_title_match or is_main_ing_match or score_ingredient_like:
                    best_score = max(max_token_score, score_main_ing, 80 if score_ingredient_like else 0)
                    matches.append((rec, best_score, fav_flag, raw_title, main_ing, ingredients, matched_tokens))
                    print(f"[DEBUG]   --> MATCHED: {raw_title} (id={rid})")
                
            if matches:
                matches.sort(key=lambda x: (x[2], x[1]), reverse=True)

                for rec, score, fav, raw_title, main_ing, ingredients, matched_tokens in matches:
                    fav_mark = "🍀" if fav else "—"

                matched_ids = [m[0]["id"] for m in matches]
                row_map = {rec["id"]: rec for rec, _, _, _, _, _, _ in matches}

                def is_excluded(dish):
                    ingredients_norm = normalize_token(dish.get("ingredients", "") or "")
                    for ex in excluded:
                        ex_norm = normalize_token(str(ex))
                        if ex_norm and ex_norm in ingredients_norm:
                            print(f"[DEBUG]     - EXCLUDED λόγω excluded υλικού: {ex_norm} in {ingredients_norm}")
                            return True
                    return False

                def exceeds_max_time(dish):
                    t = dish.get("total_time", 0) or 0
                    if max_time and t > int(max_time):
                        print(f"[DEBUG]     - EXCLUDED λόγω max_time: {t} > {max_time}")
                        return True
                    return False


                dishes_branch1 = []
                
                for mid in matched_ids:
                    if mid in row_map and mid not in seen_ids and mid not in already_suggested:
                        dish = row_map[mid]
                        if not is_excluded(dish) and not exceeds_max_time(dish):
                            dishes_branch1.append(dish)
                        else:
                            print(f"[DEBUG]     - ΚΟΠΗΚΕ μετά τα φίλτρα (excluded/max_time): {dish.get('title')} (id={dish.get('id')})")

                print(f"[DEBUG] 🎯 Branch1 NEW results (μετά το φίλτρο & excluded) = {len(dishes_branch1)}:")
                print("     ", [d["title"] for d in dishes_branch1])

                if not dishes_branch1:
                    print("[DEBUG] ⚠️ Όλα τα Branch1 matches έχουν ήδη προταθεί ή αποκλείονται λόγω excluded/max_time.")
                    conn.close()
                    return jsonify({
                        "success": False,
                        "message": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια.. Θες να το ξαναπροσπαθήσουμε;; Πες μου με τι θα ήθελες να ξεκινήσουμε!",
                        "dishes": []
                    })
                else:
                    conn.close()
                    step = data.get("step")
                    print(f"[DEBUG] ✅ Final returned from Branch1 (step={step})")

                    def enrich_dish_with_all(dish):
                        rec = dict(dish)
                        image_path = rec.get("image_path") or rec.get("image_url")
                        if image_path:
                            if not image_path.startswith("http"):
                                image_url = "/static/images/recipes/" + image_path.lstrip("/")
                            else:
                                image_url = image_path
                            rec["image_url"] = image_url
                        else:
                            rec["image_url"] = "/static/images/recipes/default.jpg"
                        chef = rec.get("chef")
                        avatar_file = CHEF_AVATAR_MAP.get(chef, "default.jpg")
                        rec["chef_avatar"] = "/static/images/avatars/" + avatar_file
                        return rec

                    if step == 2:
                        session["suggested_dish_ids"] = already_suggested + [d["id"] for d in dishes_branch1]
                        return jsonify({
                            "message": random.choice(suggestion_messages),
                            "dishes": [enrich_dish_with_all(d) for d in dishes_branch1]
                        })
                    top_dishes = dishes_branch1[:3]
                    session["suggested_dish_ids"] = already_suggested + [d["id"] for d in top_dishes]
                    return jsonify({
                        "message": random.choice(suggestion_messages),
                        "dishes": [enrich_dish_with_all(d) for d in top_dishes]
                    })
            else:
                print("[DEBUG] ❌ Branch1 no strong matches")
                conn.close()
                return jsonify({
                    "success": False,
                    "message": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια.. Θες να το ξαναπροσπαθήσουμε;; Πες μου με τι θα ήθελες να ξεκινήσουμε!",
                    "dishes": []
                })




        # =============== Branch 2: normal filtering ==================
        print("[DEBUG] ========== Branch 2 ==========")
        q = """
        SELECT recipes.*, 
               CASE WHEN fav.recipe_id IS NOT NULL THEN 1 ELSE 0 END as is_favorite
        FROM recipes
        LEFT JOIN favorite_recipes fav 
             ON fav.recipe_id = recipes.id AND fav.user_id = ?
        WHERE 1=1
        """
        params = [session.get("user_id")]

        if already_suggested:
            placeholders = ",".join("?" * len(already_suggested))
            q += f" AND recipes.id NOT IN ({placeholders})"
            params.extend(already_suggested)

        if max_time:
            try:
                q += " AND total_time <= ?"
                params.append(int(max_time))
            except Exception as e:
                print("[WARN] Invalid max_time:", e)

        if main_ingredient:
            safe_ingr = remove_tonos(main_ingredient).lower().strip()
            q += " AND (',' || LOWER(remove_tonos(ingredients)) || ',' LIKE ?)"
            params.append(f"%,{safe_ingr},%")

        if excluded:
            for item in excluded:
                s = f"%{remove_tonos(item.lower())}%"
                q += " AND remove_tonos(ingredients) NOT LIKE ?"
                params.append(s)    

        if preferred_method:
            if isinstance(preferred_method, list):
                placeholders = " OR ".join(["method LIKE ?"] * len(preferred_method))
                q += f" AND ({placeholders})"
                for m in preferred_method:
                    params.append(f"%{m}%")
            elif isinstance(preferred_method, str) and preferred_method.strip():
                q += " AND method LIKE ?"
                params.append(f"%{preferred_method.strip()}%")

        if preferred_chef:
            q += " ORDER BY is_favorite DESC, CASE WHEN chef LIKE ? THEN 0 ELSE 1 END, RANDOM()"
            params.append(f"%{preferred_chef}%")
        else:
            q += " ORDER BY is_favorite DESC, RANDOM()"

        q += " LIMIT 10"
        print("[SQL]", q)
        print("[PARAMS]", params)

        dishes_branch2 = conn.execute(q, params).fetchall()
        print(f"[DEBUG] 🍲 Branch2 returned {len(dishes_branch2)} dishes:", [d["title"] for d in dishes_branch2])
        conn.close()

        for d in dishes_branch2:
            if d["id"] not in seen_ids:
                final_dishes.append(d)

        final_dishes = final_dishes[:3]
        session["suggested_dish_ids"] = already_suggested + [d["id"] for d in final_dishes]
        print(f"[DEBUG] ✅ Final returned {len(final_dishes)} dishes:", [d["title"] for d in final_dishes])

        if not final_dishes:
            response = {
                "message": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια.. Θες να το ξαναπροσπαθήσουμε;; Πες μου με τι θα ήθελες να ξεκινήσουμε!",
                "step": 0,
                "dishes": [],
                "filters": {
                    "max_time": max_time,
                    "main_ingredient": main_ingredient,
                    "preferred_methods": preferred_method,
                    "excluded": excluded,
                    "chef": preferred_chef
                }
            }
            print("[DEBUG] ❌ No dishes found, sending fallback response:", response)
            clear_suggestions()
            return jsonify(response)

        return jsonify({
            "message": random.choice(suggestion_messages),
            "dishes": [enrich_dish_with_image_url(d) for d in final_dishes]
        })

    except Exception as e:
        print("[ERROR]", e)
        return jsonify({"error": str(e)}), 500





@app.route("/login/google/callback")
def google_login_callback():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    user_info = resp.json()
    email = user_info["email"]
    name = user_info.get("given_name", "Χρήστης")

    # Έλεγχος αν υπάρχει ήδη ο χρήστης
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()

    if existing:
        user_id = existing["id"]
    else:
        # Δημιουργία νέου χρήστη
        conn.execute(
            "INSERT INTO users (email, first_name) VALUES (?, ?)",
            (email, name)
        )
        conn.commit()
        user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]

    conn.close()
    session["user_id"] = user_id
    return redirect(url_for("welcome"))


@app.route('/delete_user_and_data', methods=['POST'])
def delete_user_and_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(success=False, error="Not logged in"), 401

    conn = sqlite3.connect(DB)
    try:
        # Διαγραφή όλων των σχετικών με τον χρήστη δεδομένων:
        conn.execute("DELETE FROM favorite_recipes WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM weekly_menu WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM weekly_goals WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM cooked_dishes WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM family_members WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM onboarding_progress WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM recipes WHERE created_by=?", (user_id,))
        conn.execute("DELETE FROM users WHERE id=?", (user_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify(success=False, error=str(e))
    conn.close()
    session.clear()
    print("User successfully deleted")
    return jsonify(success=True)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route('/delete_user_recipe', methods=['POST'])
def delete_user_recipe():
    data = request.get_json()
    recipe_id = data.get('recipe_id')
    if not recipe_id:
        return {'success': False, 'error': 'Missing recipe_id'}, 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        # 1. Διαγραφή από πίνακα αγαπημένων
        c.execute('DELETE FROM favorite_recipes WHERE recipe_id = ?', (recipe_id,))
        # 2. Διαγραφή από πίνακα συνταγών
        c.execute('DELETE FROM recipes WHERE id = ?', (recipe_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return {'success': False, 'error': str(e)}, 500

    conn.close()
    return {'success': True}

@app.route("/favorites/edit/<int:recipe_id>", methods=["GET", "POST"])
def edit_favorite_recipe(recipe_id):
    user, _ = get_user()
    user_id = user["id"]
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
    if not recipe:
        conn.close()
        return "Recipe not found", 404

    BASIC_TAGS = [
        'Κόκκινο κρέας', 'Ψάρι', 'Όσπρια', 'Λαδερά', 'Ζυμαρικά', 'Πουλερικά', 'Σαλάτα'
    ]
    tags_rows = conn.execute("SELECT tags FROM recipes WHERE tags IS NOT NULL AND tags != ''").fetchall()
    all_tags_set = set()
    for row in tags_rows:
        for tag in row["tags"].split(","):
            tag = tag.strip()
            if tag:
                all_tags_set.add(tag)
    all_tags = sorted(all_tags_set)


    add_to_favorites = request.args.get("add_to_favorites")
    if request.method == "POST":
        form = request.form
        prep = int(form.get("prep_time") or 0)
        cook = int(form.get("cook_time") or 0)
        total_time = prep + cook

        # MULTI-SELECT TAGS
        tags_list = form.getlist("tags")
        tags = ",".join([t.strip() for t in tags_list if t.strip()])

        # MULTI-SELECT COOKING METHODS
        cooking_methods_list = form.getlist("cooking_methods")
        cooking_methods = ",".join([m.strip() for m in cooking_methods_list if m.strip()])

        # MULTI-SELECT ALLERGENS
        allergens_list = form.getlist("allergens")
        if "__other__" in allergens_list:
            other = form.get("allergens_other", "").strip()
            allergens_list.remove("__other__")
            if other:
                allergens_list.append(other)            
        allergens = ",".join([a.strip() for a in allergens_list if a.strip()])

        cur = conn.cursor()
        cur.execute("""
            INSERT INTO recipes (title, ingredients, prep_time, cook_time, total_time, method, instructions, allergens, tags, created_by, parent_id, chef)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            form["title"], form["ingredients"], prep, cook, total_time,
            cooking_methods, form["instructions"], allergens, tags, user_id, recipe["id"], "Me!!"
        ))
        new_recipe_id = cur.lastrowid
        
        flag = add_to_favorites
        if flag is None:
            flag = "1"
        if flag == "1":
            cur.execute("INSERT OR IGNORE INTO favorite_recipes (user_id, recipe_id) VALUES (?, ?)", (user_id, new_recipe_id))
        cur.execute("DELETE FROM favorite_recipes WHERE user_id=? AND recipe_id=?", (user_id, recipe_id))
        conn.commit()
        conn.close()
        return redirect(url_for("favorites"))  

    conn.close()
    return render_template(
        "edit_recipe.html",
        recipe=recipe,
        all_tags=all_tags,
        all_allergs=get_all_allergens(),
        basic_tags=BASIC_TAGS,
        cooking_options=COOKING_METHODS
    )

@app.route("/reset_favorite_recipe", methods=["POST"])
def reset_favorite_recipe():
    user, _ = get_user()
    user_id = user["id"]
    data = request.get_json()
    recipe_id = data.get("recipe_id")
    parent_id = data.get("parent_id")
    if not recipe_id or not parent_id:
        return jsonify(success=False)
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        # Διαγραφή custom συνταγής
        cur.execute("DELETE FROM recipes WHERE id=? AND created_by=?", (recipe_id, user_id))
        # Βγάλε την custom από τα αγαπημένα
        cur.execute("DELETE FROM favorite_recipes WHERE user_id=? AND recipe_id=?", (user_id, recipe_id))
        # Βάλε πάλι την original (parent) στα αγαπημένα
        cur.execute("INSERT OR IGNORE INTO favorite_recipes (user_id, recipe_id) VALUES (?, ?)", (user_id, parent_id))
        conn.commit()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        print("RESET ERROR", e)
        return jsonify(success=False)

# Διαγραφή συνταγής
@app.route("/admin/recipes/delete/<int:rid>")
def delete_recipe(rid):
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM recipes WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_recipes"))

@app.route("/favorites")
@login_required
def favorites():
    return render_template("favorites.html")

@app.route("/api/favorites/filters")
@login_required
def get_favorite_filters():
    user, _ = get_user()
    user_id = user["id"]

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
    SELECT r.chef, r.main_ingredient, r.total_time, r.method
    FROM favorite_recipes f
    JOIN recipes r ON r.id = f.recipe_id
    WHERE f.user_id = ?
    """, (user_id,)).fetchall()

    conn.close()

    chefs = set()
    categories = set()
    times = set()
    methods = set()

    for r in rows:
        if r["chef"]:
            chefs.add(r["chef"])
        if r["main_ingredient"]:
            categories.add(r["main_ingredient"])
        if r["total_time"]:
            times.add(int(r["total_time"]))
        if r["method"]:
            methods.add(r["method"])

    return jsonify({
        "chefs": sorted(chefs),
        "categories": sorted(categories),
        "times": sorted(times),
        "methods": sorted(methods)
    })

@app.route("/api/last_seen/filters")
@login_required
def get_last_seen_filters():
    user, _ = get_user()
    user_id = user["id"]

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT r.chef, r.main_ingredient, r.total_time, r.method
        FROM last_seen_recipes lsr
        JOIN recipes r ON r.id = lsr.recipe_id
        WHERE lsr.user_id = ?
    """, (user_id,)).fetchall()
    conn.close()

    chefs = set()
    categories = set()
    times = set()
    methods = set()

    for r in rows:
        if r["chef"]:
            chefs.add(r["chef"])
        if r["main_ingredient"]:
            categories.add(r["main_ingredient"])
        if r["total_time"]:
            try:
                times.add(int(r["total_time"]))
            except:
                pass
        if r["method"]:
            methods.add(r["method"])

    return jsonify({
        "chefs": sorted(chefs),
        "categories": sorted(categories),
        "times": sorted(times),
        "methods": sorted(methods)
    })


@app.route('/toggle_favorite_recipe', methods=['POST'])
def toggle_favorite_recipe():
    user, _ = get_user()
    user_id = user["id"]
    data = request.get_json()
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return jsonify({"success": False})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    try:
        found = conn.execute(
            "SELECT * FROM favorite_recipes WHERE user_id=? AND recipe_id=?",
            (user_id, recipe_id)
        ).fetchone()

        if found:
            conn.execute(
                "DELETE FROM favorite_recipes WHERE user_id=? AND recipe_id=?",
                (user_id, recipe_id)
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True, "status": "removed"})
        else:
            # Προσθήκη αγαπημένης
            conn.execute(
                "INSERT INTO favorite_recipes (user_id, recipe_id) VALUES (?, ?)",
                (user_id, recipe_id)
            )
            conn.commit()
            conn.close()
            return jsonify({
                "success": True,
                "status": "added"
            })

    except Exception as e:
        conn.close()
        return jsonify({"success": False, "error": str(e)})


@app.route("/add_favorite_recipe", methods=["POST"])
def add_favorite_recipe():
    user, _ = get_user()
    user_id = user["id"]
    data = request.get_json()
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return jsonify(success=False)

    try:
        conn = sqlite3.connect(DB)
        cursor = conn.cursor()

        # Προσθήκη στο favorite_recipes
        cursor.execute(
            "INSERT OR IGNORE INTO favorite_recipes (user_id, recipe_id) VALUES (?, ?)",
            (user_id, recipe_id)
        )

        # Δημιουργία εγγραφής onboarding για favorites (αν δεν υπάρχει)
        cursor.execute(
            "SELECT 1 FROM onboarding_progress WHERE user_id = ? AND page = ?",
            (user_id, "favorites")
        )
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(
                "INSERT INTO onboarding_progress (user_id, page, step, completed) VALUES (?, ?, ?, ?)",
                (user_id, "favorites", 0, 0)
            )

        conn.commit()
        conn.close()
        return jsonify(success=True)

    except Exception as e:
        return jsonify(success=False, error=str(e))

@app.route("/delete_favorite_recipe", methods=["POST"])
def delete_favorite_recipe():
    user, _ = get_user()
    user_id = user["id"]
    data = request.get_json()
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return jsonify(success=False)
    conn = sqlite3.connect(DB)
    try:
        conn.execute("DELETE FROM favorite_recipes WHERE user_id=? AND recipe_id=?", (user_id, recipe_id))
        conn.commit()
    finally:
        conn.close()
    return jsonify(success=True)

@app.route('/delete_all_favorite_recipes', methods=['POST'])
def delete_all_favorite_recipes():
    user, _ = get_user()
    user_id = user["id"]
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM favorite_recipes WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/get_weekly_goals_status")
def get_weekly_goals_status():
    user, _ = get_user()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    today = datetime.now().date()
    last_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Φέρε στόχους χρήστη από τον πίνακα weekly_goals (με min/max)
    goals = conn.execute(
        "SELECT * FROM weekly_goals WHERE user_id=?", (user["id"],)
    ).fetchall()

    # Φέρε όλα τα πιάτα των τελευταίων 7 ημερών
    res = conn.execute("""
        SELECT cd.*, r.tags
        FROM cooked_dishes cd
        LEFT JOIN recipes r ON cd.recipe_id = r.id
        WHERE cd.user_id=?
    """, (user["id"],)).fetchall()

    # Υπολόγισε count ανά tag/κατηγορία
    counts = {}
    for row in res:
        if row['date'] not in last_7_days:
            continue
        tags = row['tags'] or ""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        for tag in tag_list:
            counts[tag] = counts.get(tag, 0) + 1

    goals_achievement = []
    for g in goals:
        cat = g["category"]
        min_times = g['min_times'] if ('min_times' in g.keys() and g['min_times'] is not None) else 1
        max_times = g['max_times'] if ('max_times' in g.keys() and g['max_times'] is not None) else 1
        n = counts.get(cat, 0)
        goals_achievement.append({
            "category": cat,
            "min_times": min_times,
            "max_times": max_times,
            "count": n
        })

    conn.close()
    return jsonify(goals_achievement)

@app.route('/add_weekly_goal', methods=['POST'])
def add_weekly_goal():
    user, _ = get_user()
    data = request.get_json()
    category = data.get('category')
    min_times = int(data.get('min_times', 1))
    max_times = int(data.get('max_times', 1))
    if not category or min_times < 0 or max_times < min_times:
        return jsonify({'status': 'error', 'msg': 'Συμπλήρωσε σωστά τα πεδία!'})
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Έλεγχος αν υπάρχει ήδη στόχος για αυτή την κατηγορία
    c.execute(
        "SELECT COUNT(*) FROM weekly_goals WHERE user_id=? AND category=?",
        (user['id'], category)
    )
    if c.fetchone()[0] > 0:
        conn.close()
        return jsonify({'status': 'error', 'msg': 'Υπάρχει ήδη στόχος για αυτή την κατηγορία!'})
    c.execute(
        "INSERT INTO weekly_goals (user_id, category, min_times, max_times) VALUES (?, ?, ?, ?)",
        (user['id'], category, min_times, max_times)
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok', 'id': c.lastrowid})

@app.route('/edit_weekly_goal', methods=['POST'])
def edit_weekly_goal():
    user, _ = get_user()
    data = request.get_json()
    goal_id = data.get('id')
    min_times = int(data.get('min_times', 1))
    max_times = int(data.get('max_times', 1))
    if not goal_id or min_times < 0 or max_times < min_times:
        return jsonify({'status': 'error', 'msg': 'Συμπλήρωσε σωστά τα πεδία!'})
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "UPDATE weekly_goals SET min_times=?, max_times=? WHERE id=? AND user_id=?",
        (min_times, max_times, goal_id, user['id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/delete_weekly_goal', methods=['POST'])
def delete_weekly_goal():
    user, _ = get_user()
    data = request.get_json()
    goal_id = data.get('id')
    if not goal_id:
        return jsonify({'status': 'error', 'msg': 'Δεν βρέθηκε στόχος!'})
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "DELETE FROM weekly_goals WHERE id=? AND user_id=?",
        (goal_id, user['id'])
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/delete_all_weekly_goals', methods=['POST'])
def delete_all_weekly_goals():
    user, _ = get_user()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "DELETE FROM weekly_goals WHERE user_id=?",
        (user['id'],)
    )
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/ingredients')
def show_ingredients():
    missing_ingredients = session.get('missing_ingredients', [])
    return render_template('ingredients.html', missing_ingredients=missing_ingredients)

@app.route("/save_missing_ingredients", methods=["POST"])
def save_missing_ingredients():
    data = request.get_json()
    prev = session.get('missing_ingredients', [])
    new_missing = data.get('missing', [])
    # Πρόσθεσε ό,τι δεν υπάρχει ήδη
    for item in new_missing:
        if item not in prev:
            prev.append(item)
    session['missing_ingredients'] = prev
    return jsonify({"status":"ok"})

# Βοηθητική συνάρτηση (για καθαρότητα)
def get_missing_ingredients():
    return session.get('missing_ingredients', [])

def save_missing_ingredients(lst):
    session['missing_ingredients'] = lst

# Προσθήκη νέου υλικού
@app.route('/add_missing_ingredient', methods=['POST'])
def add_missing_ingredient():
    item = request.json.get('item', '').strip()
    if not item:
        return jsonify({'error': 'empty'}), 400
    missing = get_missing_ingredients()
    if item not in missing:
        missing.append(item)
        save_missing_ingredients(missing)
    return jsonify({'status': 'ok'})

# Διαγραφή συγκεκριμένου υλικού
@app.route('/delete_missing_ingredient', methods=['POST'])
def delete_missing_ingredient():
    item = request.json.get('item', '').strip()
    missing = get_missing_ingredients()
    if item in missing:
        missing.remove(item)
        save_missing_ingredients(missing)
    return jsonify({'status': 'ok'})

# Διαγραφή όλων
@app.route('/delete_all_missing_ingredients', methods=['POST'])
def delete_all_missing():
    save_missing_ingredients([])
    return jsonify({'status': 'ok'})

# Βρες ΟΛΑ τα αλλεργιογόνα από τις συνταγές, χωρίς duplicates
def get_all_allergens():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    allerg_rows = conn.execute("SELECT allergens FROM recipes WHERE allergens IS NOT NULL AND allergens != ''").fetchall()
    conn.close()

    all_allergs = set()
    for row in allerg_rows:
        allergens = (row['allergens'] or '').replace(',', ' ')
        for a in allergens.split():
            a = a.strip()
            if a:
                all_allergs.add(a)
    return sorted(all_allergs)



@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user, _ = get_user()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    if request.method == "POST":
        # Λήψη τιμών από τη φόρμα
        menu_1st_day = int(request.form.get("menu_1st_day", 1))
        reset_onboarding = request.form.get("reset_onboarding") == "on"

        # Ενημέρωση user στη βάση
        conn.execute(
            "UPDATE users SET menu_1st_day=? WHERE id=?",
            (menu_1st_day, user["id"])
        )

        # Αν ζητήθηκε reset onboarding
        if reset_onboarding:
            conn.execute(
                "UPDATE onboarding_progress SET step = 0, completed = 0 WHERE user_id = ?",
                (user["id"],)
            )
        conn.commit()
        flash("Οι ρυθμίσεις αποθηκεύτηκαν.", "success")
        return redirect("/settings")

    # Φέρε ενημερωμένο χρήστη
    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user["id"],)
    ).fetchone()

    conn.close()

    return render_template("settings.html", user=user)


@app.route("/profile_completion_percent")
@login_required
def profile_completion_percent():
    user, members = get_user()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    goals = conn.execute("SELECT * FROM weekly_goals WHERE user_id=?", (user["id"],)).fetchall()
    conn.close()

    filled = 0
    total = 7  

    if user["first_name"]: filled += 1
    if user["chef"]: filled += 1
    if user["menu_day"] and user["menu_hour"]: filled += 1
    if user["cooking_method"]: filled += 1
    if len(members) > 0: filled += 1
    if len(goals) > 0: filled += 1

    # ✅ Νέος έλεγχος: τουλάχιστον ένας χρόνος μαγειρέματος
    cooktime_days = ['mon','tue','wed','thu','fri','sat','sun']
    if any(user[f'cooktime_{d}'] not in (None, 0, '', '0') for d in cooktime_days):
        filled += 1


    percent = int((filled / total) * 100)
    return jsonify({"completion": percent})

@app.route("/edit_profile_info", methods=["POST"])
def edit_profile_info():
    user, _ = get_user()
    data = request.get_json()

    # Κανονικοποίηση τιμών
    first_name = data.get("first_name", "").strip()
    family_name = data.get("family_name", "").strip()
    address = data.get("address", "").strip()
    alt_address = data.get("alt_address", "").strip()

    chef = data.get("chef")
    if chef in ("", None, "-- Επιλέξτε --"): chef = None

    menu_day = data.get("menu_day")
    if menu_day in ("", None, "-- Μέρα --"): menu_day = None

    menu_hour = data.get("menu_hour")
    if menu_hour in ("", None, "-- Ώρα --"): menu_hour = None

    cooking_method = data.get("cooking_method", "").strip()

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        UPDATE users SET first_name=?, family_name=?, address=?, alt_address=?, chef=?, menu_day=?, menu_hour=?, cooking_method=?
        WHERE id=?
    """, (
        first_name, family_name, address, alt_address,
        chef, menu_day, menu_hour, cooking_method,
        user["id"]
    ))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/add_family_member', methods=['POST'])
def add_family_member():
    user, _ = get_user()
    data = request.get_json()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO family_members (user_id, name, age, allergies) VALUES (?, ?, ?, ?)",
        (user['id'], data['name'], int(data['age']), data['allergies'])
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "id": new_id})

@app.route('/edit_family_member', methods=['POST'])
def edit_family_member():
    user, _ = get_user()
    data = request.get_json()
    conn = sqlite3.connect(DB)
    conn.execute(
        "UPDATE family_members SET name=?, age=?, allergies=? WHERE id=? AND user_id=?",
        (data['name'], int(data['age']), data['allergies'], data['member_id'], user['id'])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/delete_family_member', methods=['POST'])
def delete_family_member():
    user, _ = get_user()
    data = request.get_json()
    conn = sqlite3.connect(DB)
    conn.execute(
        "DELETE FROM family_members WHERE id=? AND user_id=?",
        (data['member_id'], user['id'])
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/edit_cooking_times", methods=["POST"])
def edit_cooking_times():
    user, _ = get_user()
    data = request.get_json()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    sql = "UPDATE users SET cooktime_mon=?, cooktime_tue=?, cooktime_wed=?, cooktime_thu=?, cooktime_fri=?, cooktime_sat=?, cooktime_sun=? WHERE id=?"
    cur.execute(sql, (
        data.get("cooktime_mon", 0), data.get("cooktime_tue", 0), data.get("cooktime_wed", 0),
        data.get("cooktime_thu", 0), data.get("cooktime_fri", 0), data.get("cooktime_sat", 0), data.get("cooktime_sun", 0),
        user["id"]
    ))
    conn.commit()
    conn.close()
    return jsonify({"status":"ok"})

@app.route("/chat", methods=["POST"])
def chat():
    user, _ = get_user()
    msg = request.form.get("message")
    answer = f"Έλαβες: {msg}"
    now = datetime.now()
    days_map = {
        "Monday": "Δευτέρα", "Tuesday": "Τρίτη", "Wednesday": "Τετάρτη",
        "Thursday": "Πέμπτη", "Friday": "Παρασκευή",
        "Saturday": "Σάββατο", "Sunday": "Κυριακή"
    }
    current_day = days_map[now.strftime("%A")]
    greeting = "Καλημέρα" if now.hour < 12 else "Καλησπέρα"
    return render_template("welcome.html", greeting=greeting, user_name=user["first_name"], current_day=current_day, chat_response=answer)

def get_current_week_start():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.date()

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.date()

def normalize_title(title):
    if not title:
        return ""
    # Αφαίρεση τόνων και μετατροπή σε μικρά, καθαρισμός
    t = ''.join(c for c in unicodedata.normalize('NFD', title) if unicodedata.category(c) != 'Mn')
    return t.lower().strip()

@app.route("/menu")
@login_required
def menu():
    user, members = get_user()
    user_id = user["id"]
    week_start = get_current_week_start()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    def split_and_strip(s):
        return set(x.strip().lower() for x in (s or '').split(',') if x.strip())

    # Πάρε το αποθηκευμένο μενού (αν υπάρχει)
    c = conn.execute(
        "SELECT * FROM weekly_menu WHERE user_id=? AND week_start_date=? ORDER BY day_of_week ASC",
        (user_id, str(week_start))
    )
    saved_menu = c.fetchall()

    fav_rows = conn.execute("SELECT recipe_id FROM favorite_recipes WHERE user_id=?", (user_id,)).fetchall()
    fav_ids = set(r["recipe_id"] for r in fav_rows)
    menu_entries = []
    categories = ['κόκκινο κρέας', 'ψάρι', 'όσπρια', 'λαδερά', 'ζυμαρικά', 'πουλερικά', 'σαλάτα', 'delivery']
    preferred_methods = [m.strip().lower() for m in (user["cooking_method"] or "").split(",") if m.strip()]
    fav_chef = (user["chef"] or "").strip()

    cooktimes = []
    for d in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
        val = user[f"cooktime_{d}"] if f"cooktime_{d}" in user.keys() else None
        try:
            cooktimes.append(int(val))
        except (TypeError, ValueError):
            cooktimes.append(60)

    for entry in saved_menu:
        recipe = None
        if entry["recipe_id"]:
            recipe = conn.execute("SELECT * FROM recipes WHERE id=?", (entry["recipe_id"],)).fetchone()

        category = ""
        if recipe:
            category = (recipe["main_dish_tag"] or "").capitalize()
            if not category:
                for cat in categories:
                    if cat in (recipe["tags"] or "").lower():
                        category = cat.capitalize()
                        break

        try:
            day_idx = int(entry["day_of_week"])
        except:
            day_idx = 0

        criteria_text = []
        if recipe and recipe["total_time"] and abs(int(recipe["total_time"]) - cooktimes[day_idx]) <= 10:
            criteria_text.append("✓ χρόνος OK")
        elif recipe and recipe["total_time"]:
            criteria_text.append("✓ χρόνος σχετικός")

        if recipe:
            dish_methods = [m.strip().lower() for m in (recipe["method"] or "").split(",") if m.strip()]
            if dish_methods and all(dm in preferred_methods for dm in dish_methods):
                criteria_text.append("✓ τρόπος")

        if recipe and fav_chef and fav_chef.lower() in (recipe["chef"] or "").lower():
            criteria_text.append("✓ σεφ")

        criteria = ", ".join(criteria_text) if criteria_text else "-"

        menu_entries.append({
            "day": WEEKDAYS_GR[entry["day_of_week"]],
            "title": recipe["title"] if recipe else entry["title"] if "title" in entry.keys() else "Δεν βρέθηκε πιάτο",
            "chef": recipe["chef"] if recipe else "",
            "prep_time": recipe["prep_time"] if recipe else "-",
            "cook_time": recipe["cook_time"] if recipe else "-",
            "duration": recipe["total_time"] if recipe else "-",
            "method": recipe["method"] if recipe else "-",
            "url": recipe["url"] if recipe else "",
            "criteria": criteria,
            "ingredients": recipe["ingredients"] if recipe else "-",
            "instructions": recipe["instructions"] if recipe else "-",
            "menu_id": entry["id"] if recipe else "-",
            "tags": recipe["tags"] if recipe else "",
            "category": category if recipe else "-",
            "is_favorite": (recipe["id"] in fav_ids) if recipe else False,
            "recipe_id": recipe["id"] if recipe else None
        })

    # Στόχοι & αλλεργίες
    weekly_goals = conn.execute("SELECT * FROM weekly_goals WHERE user_id=?", (user_id,)).fetchall()
    goals_achievement = []
    for g in weekly_goals:
        cat = g["category"].strip().lower()
        min_times = g["min_times"]
        max_times = g["max_times"]
        count_in_menu = sum(
            1 for r in menu_entries if r and cat in (r["tags"] or '').lower()
        )
        goals_achievement.append({
            "category": cat,
            "min_times": min_times,
            "max_times": max_times,
            "count": count_in_menu
        })

    # Ανέφικτοι στόχοι
    all_recipes = [dict(r) for r in conn.execute("SELECT * FROM recipes").fetchall()]
    all_allergies = set()
    for m in members:
        if m["allergies"]:
            all_allergies.update(split_and_strip(m["allergies"]))

    valid_recipes = []
    for r in all_recipes:
        allergens_in_recipe = split_and_strip(r.get("allergens", ""))
        if not (all_allergies & allergens_in_recipe):
            valid_recipes.append(r)

    unreachable_goals = []
    for g in weekly_goals:
        cat = g["category"].strip().lower()
        available = [r for r in valid_recipes if cat in (r["tags"] or '').lower()]
        if not available:
            unreachable_goals.append(cat)


    # Φέρε τη μέρα έναρξης από τον πίνακα users
    menu_1st_day = conn.execute(
        "SELECT menu_1st_day FROM users WHERE id = ?",
        (user["id"],)
    ).fetchone()["menu_1st_day"]

    conn.close()

    show_success_modal = 0
    show_success_modal = request.args.get("created") == "1"
    
    return render_template(
        "menu.html",
        menu=menu_entries,
        goals_achievement=goals_achievement,
        unreachable_goals=unreachable_goals,
        menu_1st_day=menu_1st_day,
        show_success_modal=show_success_modal
    )

def create_weekly_menu(user, members):
    user_id = user["id"]
    week_start = get_current_week_start()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    def split_and_strip(s):
        return set(x.strip().lower() for x in (s or '').split(',') if x.strip())

    preferred_methods = [m.strip().lower() for m in (user["cooking_method"] or "").split(",") if m.strip()]
    fav_chef = (user["chef"] or "").strip()
    cooktimes = []
    for d in ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']:
        val = user[f"cooktime_{d}"] if f"cooktime_{d}" in user.keys() else None
        try:
            cooktimes.append(int(val))
        except (TypeError, ValueError):
            cooktimes.append(default_minutes)
    weekly_goals = conn.execute("SELECT * FROM weekly_goals WHERE user_id=?", (user_id,)).fetchall()
    goals = []
    for g in weekly_goals:
        goals.append({
            "category": g["category"].strip().lower(),
            "min_times": g["min_times"],
            "max_times": g["max_times"]
        })

    c = conn.execute("SELECT * FROM recipes")
    all_recipes = [dict(r) for r in c.fetchall()]
    all_allergies = set()
    for m in members:
        if m["allergies"]:
            all_allergies.update(split_and_strip(m["allergies"]))

    valid_recipes = []
    for r in all_recipes:
        allergens_in_recipe = split_and_strip(r.get("allergens", ""))
        if not (all_allergies & allergens_in_recipe):
            valid_recipes.append(r)

    used_ids = set()
    used_titles = set()
    used_tags = set()
    week_menu = [None] * 7
    categories = ['κόκκινο κρέας', 'ψάρι', 'όσπρια', 'λαδερά', 'ζυμαρικά', 'πουλερικά', 'σαλάτα', 'delivery']
    category_counts = {cat: 0 for cat in categories}
    sorted_days = sorted([(i, cooktimes[i]) for i in range(7)], key=lambda x: x[1])

    # 1. Ικανοποίησε min_times
    for goal in goals:
        cat = goal["category"]
        min_times = goal["min_times"]
        days_left = [i for i, _ in sorted_days if week_menu[i] is None]
        added = 0
        for i in days_left:
            if added >= min_times:
                break
            day_time = cooktimes[i]
            matches = [
                r for r in valid_recipes
                if cat in (r["tags"] or '').lower()
                and r["id"] not in used_ids
                and normalize_title(r["title"]) not in used_titles
                and (r.get("main_dish_tag", "").lower() not in used_tags if r.get("main_dish_tag") else True)
                and r.get("total_time") is not None
                and abs(int(r["total_time"]) - day_time) <= 30
            ]
            matches = sorted(matches, key=lambda r: abs(int(r["total_time"]) - day_time))
            if not matches:
                continue
            chosen = matches.pop(0)
            week_menu[i] = chosen
            used_ids.add(chosen["id"])
            used_titles.add(normalize_title(chosen["title"]))
            if chosen.get("main_dish_tag"):
                used_tags.add(chosen["main_dish_tag"].lower())
            for category in categories:
                if category in (chosen["tags"] or '').lower():
                    category_counts[category] += 1
            added += 1

    # 2. Συμπλήρωσε τα υπόλοιπα
    for i, _ in sorted_days:
        if week_menu[i] is not None:
            continue
        day_time = cooktimes[i]
        candidates = []
        for r in valid_recipes:
            if r["id"] in used_ids:
                continue
            if normalize_title(r["title"]) in used_titles:
                continue
            if r.get("main_dish_tag") and r["main_dish_tag"].lower() in used_tags:
                continue
            skip = False
            for goal in goals:
                cat = goal["category"]
                cat_in_recipe = cat in (r["tags"] or '').lower()
                count_now = category_counts[cat]
                if cat_in_recipe and count_now >= goal["max_times"]:
                    skip = True
                    break
            if skip:
                continue
            score = 0
            if r["total_time"]:
                diff = abs(int(r["total_time"]) - day_time)
                if diff > 30:
                    continue
                elif diff <= 10:
                    score += 5
                elif diff <= 20:
                    score += 2
            if preferred_methods and any(pm in (r["method"] or '').lower() for pm in preferred_methods):
                score += 2
            if fav_chef and fav_chef.lower() in (r["chef"] or "").lower():
                score += 1
            candidates.append((score, r))

        candidates = sorted(candidates, key=lambda x: -x[0])
        chosen = None
        if candidates and candidates[0][0] > 0:
            top_score = candidates[0][0]
            top_candidates = [r for s, r in candidates if s == top_score]
            chosen = random.choice(top_candidates)
        elif valid_recipes:
            unused = [
                r for r in valid_recipes
                if r["id"] not in used_ids
                and normalize_title(r["title"]) not in used_titles
                and (r.get("main_dish_tag", "").lower() not in used_tags if r.get("main_dish_tag") else True)
            ]
            if unused:
                chosen = random.choice(unused)
        if chosen:
            week_menu[i] = chosen
            used_ids.add(chosen["id"])
            used_titles.add(normalize_title(chosen["title"]))
            if chosen.get("main_dish_tag"):
                used_tags.add(chosen["main_dish_tag"].lower())
            for category in categories:
                if category in (chosen["tags"] or '').lower():
                    category_counts[category] += 1

    # 3. Save στη βάση
    for i, day in enumerate(WEEKDAYS_GR):
        chosen = week_menu[i]
        if chosen:
            criteria_text = []
            if chosen["total_time"] and abs(int(chosen["total_time"]) - cooktimes[i]) <= 10:
                criteria_text.append("✓ χρόνος OK")
            elif chosen["total_time"]:
                criteria_text.append("✓ χρόνος σχετικός")
            πιατο_methods = [(m.strip().lower()) for m in (chosen["method"] or "").split(",") if m.strip()]
            if preferred_methods:
                if all(pm in preferred_methods for pm in πιατο_methods):
                    criteria_text.append("✓ τρόπος")
            if fav_chef and fav_chef.lower() in (chosen["chef"] or "").lower():
                criteria_text.append("✓ σεφ")
            criteria = ", ".join(criteria_text) if criteria_text else "-"
            conn.execute("""
                INSERT INTO weekly_menu (user_id, week_start_date, day_of_week, recipe_id, criteria)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, str(week_start), i, chosen["id"], criteria))
        else:
            conn.execute("""
                INSERT INTO weekly_menu (user_id, week_start_date, day_of_week, recipe_id, criteria)
                VALUES (?, ?, ?, NULL, ?)
            """, (user_id, str(week_start), i, "Δεν πληρούνται τα βασικά κριτήρια"))

    conn.commit()
    conn.close()

@app.route("/generate_menu", methods=["POST"])
def generate_menu():
    user, members = get_user()
    user_id = user["id"]
    week_start = get_current_week_start()

    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM weekly_menu WHERE user_id=? AND week_start_date=?", (user_id, str(week_start)))
    conn.commit()
    conn.close()

    create_weekly_menu(user, members)

    return redirect(url_for("menu", created=1))

@app.route('/swap_menu_entries', methods=['POST'])
def swap_menu_entries():
    data = request.get_json()
    menu_id_from = data.get('menu_id_from')
    menu_id_to = data.get('menu_id_to')
    if not menu_id_from or not menu_id_to:
        return jsonify(success=False)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Πάρε τα recipe_id των δύο ημερών
    c.execute("SELECT recipe_id FROM weekly_menu WHERE id=?", (menu_id_from,))
    rec_from = c.fetchone()
    c.execute("SELECT recipe_id FROM weekly_menu WHERE id=?", (menu_id_to,))
    rec_to = c.fetchone()
    if rec_from is None or rec_to is None:
        conn.close()
        return jsonify(success=False)
    # Swap τα recipe_id
    c.execute("UPDATE weekly_menu SET recipe_id=? WHERE id=?", (rec_to[0], menu_id_from))
    c.execute("UPDATE weekly_menu SET recipe_id=? WHERE id=?", (rec_from[0], menu_id_to))
    conn.commit()
    conn.close()
    return jsonify(success=True)

def remove_tonos(s):
    if not s:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    ).lower()

@app.route("/update_menu_entries", methods=["POST"])
def update_menu_entries():
    data = request.get_json()
    updates = data.get("updates", [])
    ignore_allergy = data.get("ignore_allergy", False)
    if not updates:
        return jsonify({"success": False})

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Πάρε τα μέλη και τις αλλεργίες τους
    members = conn.execute("SELECT name, allergies FROM family_members").fetchall()

    recipes = conn.execute("SELECT id, title, tags, main_dish_tag, ingredients, allergens FROM recipes").fetchall()

    allergy_warnings = []
    # Κρατάμε mapping: recipe_title -> (allergen, member name)
    title_to_id = {remove_tonos(r["title"]): r for r in recipes}

    # Πρώτα ελέγχει για αλλεργιογόνα, αν δεν αγνοούνται (ignore_allergy)
    if not ignore_allergy:
        for update in updates:
            recipe_title = update.get("recipe_title", "").strip()
            norm_input = remove_tonos(recipe_title)
            chosen_recipe = None
            for r in recipes:
                if remove_tonos(r["title"]) == norm_input:
                    chosen_recipe = r
                    break
                if r["main_dish_tag"] and remove_tonos(r["main_dish_tag"]) == norm_input:
                    chosen_recipe = r
                    break
                if (remove_tonos(r["tags"] or "").find(norm_input) != -1) or \
                   (remove_tonos(r["ingredients"] or "").find(norm_input) != -1):
                    chosen_recipe = r
                    break
            if chosen_recipe:
                recipe_allergens = (chosen_recipe["allergens"] or "").lower().split(",")
                recipe_allergens = [remove_tonos(a.strip()) for a in recipe_allergens if a.strip()]
                if recipe_allergens:
                    for m in members:
                        if not m["allergies"]:
                            continue
                        user_allergies = [remove_tonos(a.strip()) for a in m["allergies"].split(",") if a.strip()]
                        found_common = set(recipe_allergens) & set(user_allergies)
                        if found_common:
                            allergy_warnings.append({
                                "dish": chosen_recipe["title"],
                                "member": m["name"],
                                "allergen": ", ".join(found_common)
                            })
        if allergy_warnings:
            conn.close()
            return jsonify({"success": False, "allergy_warnings": allergy_warnings})

    # Αποθήκευση αλλαγών (μόνο αφού περάσει το allergy check ή αν το αγνοήσουμε)
    for update in updates:
        menu_id = update.get("menu_id")
        recipe_title = update.get("recipe_title", "").strip()
        if not menu_id or not recipe_title:
            continue
        norm_input = remove_tonos(recipe_title)
        found = None
        for r in recipes:
            if remove_tonos(r["title"]) == norm_input:
                found = r
                break
            if r["main_dish_tag"] and remove_tonos(r["main_dish_tag"]) == norm_input:
                found = r
                break
            if (remove_tonos(r["tags"] or "").find(norm_input) != -1) or \
               (remove_tonos(r["ingredients"] or "").find(norm_input) != -1):
                found = r
                break
        if found:
            conn.execute(
                "UPDATE weekly_menu SET recipe_id=? WHERE id=?",
                (found["id"], menu_id)
            )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/get_recipes_for_autocomplete")
def get_recipes_for_autocomplete():
    user, _ = get_user()
    user_id = user["id"]

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, title, chef, tags, ingredients, main_dish_tag
        FROM recipes
        WHERE created_by = 0 OR created_by = ?
    """, (user_id,)).fetchall()

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "title": r["title"],
            "chef": r["chef"],
            "tags": r["tags"] or "",
            "ingredients": r["ingredients"] or "",
            "main_dish_tag": r["main_dish_tag"] or ""
        })

    conn.close()
    return jsonify(result)

@app.route('/clear_suggestions', methods=['POST'])
def clear_suggestions():
    session.pop('suggested_dish_ids', None)
    print("suggestions cleared")
    return jsonify({"status": "ok"})

@app.route("/history")
@login_required
def cooked_history():
    user, _ = get_user()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    BASIC_CATEGORIES = [
        'Κόκκινο κρέας', 'Ψάρι', 'Όσπρια', 'Λαδερά', 'Ζυμαρικά', 'Πουλερικά', 'Σαλάτα'
    ]

    res = conn.execute("""
        SELECT cd.*,
               r.id AS recipe_id,
               r.chef,
               r.tags,
               r.total_time,
               r.method,
               r.prep_time,
               r.cook_time,
               r.ingredients,
               r.instructions,
               r.url,
               r.main_dish_tag
        FROM cooked_dishes cd
        LEFT JOIN recipes r ON cd.recipe_id = r.id
        WHERE cd.user_id=?
        ORDER BY cd.date DESC, cd.recorded_at DESC
    """, (user["id"],)).fetchall()

    favorite_ids = set(
        row[0] for row in conn.execute(
            "SELECT recipe_id FROM favorite_recipes WHERE user_id=?", (user["id"],)
        ).fetchall()
    )

    history = []
    for row in res:
        tags = row['tags'] or ""
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        basic_category = next((t for t in tag_list if t in BASIC_CATEGORIES), "-")
        d = dict(row)
        d['basic_category'] = basic_category
        rec_id = d.get('recipe_id')
        d['is_favorite'] = rec_id in favorite_ids if rec_id else False
        history.append(d)

    today = datetime.now().date()
    days_to_check = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 3)]
    existing_dates = [row['date'] for row in history]
    missing_days = [d for d in days_to_check if d not in existing_dates]
    conn.close()

    return render_template('history.html', history=history, missing_days=missing_days)


@app.route('/delete_history_entry', methods=['POST'])
def delete_history_entry():
    user, _ = get_user()
    data = request.get_json()
    entry_id = data.get('id')
    if not entry_id:
        return {'status': 'error'}
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM cooked_dishes WHERE id=? AND user_id=?", (entry_id, user["id"]))
    conn.commit()
    conn.close()
    print("entry deleted")
    return {'status': 'ok'}

@app.route("/add_manual_recipe", methods=["POST"])
def add_manual_recipe():
    user, _ = get_user()
    data = request.get_json()
    title = data["title"].strip()
    date = data["date"]
    recipe_id = data.get("recipe_id")  # <-- μπορεί να είναι None

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    is_new = False
    if not recipe_id:
        # Δημιούργησε νέα συνταγή (ο τίτλος είναι υποχρεωτικός)
        c.execute("INSERT INTO recipes (title, chef, created_by) VALUES (?, ?, ?)",
                  (title, "Me!!", user["id"]))
        recipe_id = c.lastrowid
        is_new = True
    else:
        # Εναλλακτικά: πάρε τον τίτλο από τη βάση (και αγνόησε ό,τι σου έστειλε ο client)
        c.execute("SELECT title FROM recipes WHERE id=?", (recipe_id,))
        r = c.fetchone()
        if r:
            title = r["title"]
        else:
            return jsonify({"status": "error", "message": "Invalid recipe_id"}), 400

    # Καταχώρησε το πιάτο στο ιστορικό
    c.execute("INSERT INTO cooked_dishes (user_id, date, recipe_id, title) VALUES (?, ?, ?, ?)",
              (user["id"], date, recipe_id, title))
    cooked_dish_id = c.lastrowid

    # Βρες info για απάντηση
    c.execute("SELECT chef, tags FROM recipes WHERE id=?", (recipe_id,))
    recipe_row = c.fetchone()
    chef = recipe_row["chef"] if recipe_row and recipe_row["chef"] else "-"
    tags = recipe_row["tags"] if recipe_row and recipe_row["tags"] else ""

    BASIC_CATEGORIES = [
        'Κόκκινο κρέας', 'Ψάρι', 'Όσπρια', 'Λαδερά', 'Ζυμαρικά', 'Πουλερικά', 'Σαλάτα'
    ]
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    basic_category = next((t for t in tag_list if t in BASIC_CATEGORIES), "-")

    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "new_recipe": is_new,
        "recipe_id": recipe_id,
        "id": cooked_dish_id,
        "date": date,
        "title": title,
        "chef": chef,
        "basic_category": basic_category
    })

@app.route('/cook_dish', methods=['POST'])
def cook_dish():
    user, _ = get_user()
    data = request.get_json()
    recipe_id = str(data.get('recipe_id'))      # Βεβαιώσου ότι είναι string!
    title = data.get('title', '')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    user_id = user["id"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, title, recipe_id FROM cooked_dishes WHERE user_id=? AND date=?", (user_id, date))
    found = c.fetchone()
    if found:
        old_recipe_id = str(found[2]) if found[2] is not None else ""
        old_title = found[1]
#        print("DEBUG: recipe_id from JS:", recipe_id, "old_recipe_id from DB:", old_recipe_id)
        # Έλεγχος για ίδιο πιάτο
        if recipe_id == old_recipe_id:
            conn.close()
            return jsonify({"exists": True, "already": True, "old_title": old_title})
        else:
            conn.close()
            return jsonify({"exists": True, "already": False, "old_title": old_title})
    else:
        c.execute("INSERT INTO cooked_dishes (user_id, date, recipe_id, title) VALUES (?, ?, ?, ?)", (user_id, date, recipe_id, title))
        conn.commit()
        conn.close()
        return jsonify({"exists": False})

@app.route('/update_cooked_dish', methods=['POST'])
def update_cooked_dish():
    data = request.get_json()
    title = data.get('title')
    date = data.get('date')
    user, _ = get_user()
    user_id = user["id"]
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        # ΠΡΟΣΟΧΗ: Update *υπάρχουσας* εγγραφής, όχι insert!
        cur.execute("UPDATE cooked_dishes SET title=? WHERE user_id=? AND date=?", (title, user_id, date))
        if cur.rowcount == 0:
            # Δεν βρέθηκε εγγραφή να αλλάξει
            conn.close()
            return jsonify(success=False, message="Δεν βρέθηκε εγγραφή για ενημέρωση.")
        conn.commit()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        print("UPDATE ERROR:", e)
        return jsonify(success=False, message=str(e))

@app.route("/get_recipe/<int:recipe_id>")
def get_recipe(recipe_id):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
    conn.close()
    if not r:
        return jsonify({})
    return jsonify({
        "title": r["title"],
        "chef": r["chef"],
        "ingredients": r["ingredients"],
        "prep_time": r["prep_time"],
        "cook_time": r["cook_time"],
        "method": r["method"],
        "instructions": r["instructions"],
        "category": r["main_dish_tag"],
        "tags": r["tags"],
        "allergens": r["allergens"],
        "title": r["title"],
        "url": r["url"],
        "parent_id": r["parent_id"] 
    })

@app.template_filter('todate')
def todate_filter(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


@app.route("/page-flip-transition")
def page_flip_transition():
    return render_template("page-flip-transition.html")


####----ΟNBOARDING----####
@app.route("/api/onboarding_progress")
def get_all_onboarding_progress():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT page, step, completed FROM onboarding_progress WHERE user_id=?", (user_id,)).fetchall()
    conn.close()

    data = {row["page"]: {"step": row["step"], "completed": bool(row["completed"])} for row in rows}
    return jsonify(data)

@app.route("/api/onboarding_create_if_needed", methods=["POST"])
def onboarding_create_if_needed():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    page = request.json.get("page", "").strip()
    if not page:
        return jsonify({"error": "Missing page"}), 400

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        INSERT OR IGNORE INTO onboarding_progress (user_id, page)
        VALUES (?, ?)
    """, (user_id, page))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/onboarding_update_step", methods=["POST"])
def onboarding_update_step():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    page = data.get("page", "").strip()
    step = data.get("step")

    if not page or step is None:
        return jsonify({"error": "Missing page or step"}), 400

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        UPDATE onboarding_progress
        SET step = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND page = ?
    """, (step, user_id, page))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/onboarding_mark_completed", methods=["POST"])
def onboarding_mark_completed():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    page = request.json.get("page", "").strip()
    if not page:
        return jsonify({"error": "Missing page"}), 400

    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("""
        UPDATE onboarding_progress
        SET completed = 1, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND page = ?
    """, (user_id, page))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

####----ΟNBOARDING----####

if __name__ == "__main__":
    app.run(debug=True)


