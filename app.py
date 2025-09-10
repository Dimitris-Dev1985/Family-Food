from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, get_flashed_messages
import sqlite3, unicodedata, random, re, json, traceback, os, openai
from dotenv import load_dotenv
from rapidfuzz import fuzz, process
from datetime import datetime, timedelta
from jinja2 import pass_context
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_mail import Mail, Message
from stopwords_gr import RAW_STOPWORDS

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
default_minutes = 60

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

import requests

# Δημιουργούμε custom requests session που παρακάμπτει το SSL verification
req_session = requests.Session()
req_session.verify = False  # ⚠️ απενεργοποίηση SSL validation

# Το περνάμε στον OpenAI client
openai.requestssession = req_session



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

        "Your ONLY task is to manage and update these 5 fields:\n"
        "- max_time (integer minutes) - είναι ο χρόνος που έχει στη διάθεσή του ο χρήστης για μαγείρεμα (απαραίτητο να υπάρχει πάντα)\n"
        "- main_ingredient (string) - είναι το βασικό υλικό που θέλει να χρησιμοποιήσει ο χρήστης. Θα το βρείτε ΜΑΖΙ.\n"
        "- aux_ingredients (array) - είναι τα επιπλέον βοηθητικά υλικά που θέλει ο χρήστης να έχει η συνταγή (προσθέσεις ή αφαιρέσεις)\n"
        "- cooking_method (array) - είναι λίστα προκαθορισμένων μεθόδων μαγειρέματος που μπορεί να χρειαστεί να επεξεργαστείς (προσθέσεις ή αφαιρέσεις)\n"
        "- excluded_keywords (array) - είναι λίστα με λέξεις που μπορεί να χρειαστεί να επεξεργαστείς (προσθέσεις ή αφαιρέσεις)\n\n"

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
        "7. If the user explicitly mentions a material as the desired dish base (π.χ. 'σε ψάρι', 'κοτόπουλο', 'μοσχάρι με πατάτες'), you MUST ADD it as main_ingredient and (if present) REMOVE from excluded_keywords.\n"
        "8. If user decides that finally has a material available that was previously missing → REMOVE from excluded_keywords AND add it to either main_ingredients OR aux_ingredient.\n"           
        "9. If the user explicitly mentions a cooking method (π.χ. 'στο φούρνο', 'σε σχάρα', 'με air fryer'), you MUST always include it in cooking_method.\n"
        "10. If the user explicitly says he wants to AVOID a cooking method (π.χ. 'όχι φούρνο', 'χωρίς τηγάνι', 'δεν θέλω σχάρα'), you must REMOVE that method from cooking_method.\n"
        "11. If aux_ingredients, cooking_method or excluded_keywords is not clearly updated, don't include them in your answer.\n"
        "12. Regarding time:\n"
            "- If the user specifies an *absolute time* → take it literally (π.χ. 'μισή ώρα'=30, 'μιάμιση ώρα'=90).\n"
            "- If the user speaks about *relative time* compared to the existing (π.χ. 'πιο γρήγορο', 'πιο αργά', 'συντομότερο'), do NOT invent arbitrary numbers, but adjust the current max_time value by up to ±20%.\n"
            "(e.g. if current time = 200 and user says 'πιο γρήγορο' → new time = 160 (20% less).\n"
    )


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

@app.route('/recipe_page/<int:recipe_id>')
def recipe_page(recipe_id):
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
               COALESCE(instructions,'') as instructions
        FROM recipes
        WHERE id = ?
    """, (recipe_id,)).fetchone()

    if not recipe:
        return "Recipe not found", 404

    # Υλικά
    ingredients = [line.strip() for line in recipe['ingredients'].splitlines() if line.strip()]
    print("[DB] ingredients list:", ingredients)

    # Οδηγίες
    instructions = [line.strip() for line in recipe['instructions'].splitlines() if line.strip()]
    print("[DB] instructions list:", instructions)

    # Εικόνα από static folder
    image_url = url_for('static', filename=f'images/recipes/{recipe['id']}.jpg')

    # ========== ΕΛΕΓΧΟΣ FAVORITE ==========
    is_favorite = False
    user_id = session.get('user_id')
    if user_id:
        fav_row = conn.execute(
            "SELECT 1 FROM favorite_recipes WHERE user_id = ? AND recipe_id = ?",
            (user_id, recipe_id)
        ).fetchone()
        is_favorite = fav_row is not None

    # Κλείσιμο connection για ασφάλεια
    conn.close()

    return render_template(
        'recipe_page.html',
        recipe=recipe,
        ingredients=ingredients,
        instructions=instructions,
        image_url=image_url,
        is_favorite=is_favorite
    )

@app.route('/api/similar')
def api_similar():
    recipe_id = request.args.get("recipe_id", type=int)
    if not recipe_id:
        return {"success": False, "error": "Missing recipe_id"}, 400

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    similar = conn.execute("""
        SELECT id, title, chef
        FROM recipes
        WHERE dish_category = (SELECT dish_category FROM recipes WHERE id = ?)
          AND id != ?
        ORDER BY RANDOM()
        LIMIT 3
    """, (recipe_id, recipe_id)).fetchall()

    data = []
    for row in similar:
        data.append({
            "id": row["id"],
            "title": row["title"],
            "chef": row["chef"],
            "image_url": url_for('static', filename=f'images/recipes/{row["id"]}.jpg')
        })

    return {"success": True, "recipes": data}

@app.route("/get_main_tags")
def get_main_tags():
    category = request.args.get("category")
    print("[DEBUG] 🔍 GET /get_main_tags called with category =", category)

    if not category:
        print("[WARN] ❗ No category provided")
        return jsonify({"tags": []}), 400

    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("""
            SELECT DISTINCT main_dish_tag
            FROM recipes
            WHERE dish_category LIKE ?
              AND main_dish_tag IS NOT NULL
              AND main_dish_tag != ''
        """, (f"%{category}%",))
        rows = c.fetchall()
        conn.close()

        tags = sorted(set(r[0].strip() for r in rows if r[0] and r[0].strip()))
#        print(f"[DEBUG] ✅ Found {len(tags)} tags for category '{category}':", tags)
        return jsonify({"tags": tags})
    
    except Exception as e:
        print("[ERROR] ❌ Failed to fetch main tags:", e)
        return jsonify({"tags": []}), 500

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

        print(f"[STATE] max_time={current_max_time}, ingredient={current_main_ingredient}, method={current_cooking_method}, excluded={excluded_keywords}, aux={aux_ingredients}")
        if not message:
            return jsonify({"error": "Empty message"}), 400

        msg_norm = normalize(message)
        system_prompt = SYSTEM_PROMPT
        user_context = f"Current state:\n- max_time: {current_max_time}\n- main_ingredient: {current_main_ingredient}\n- cooking_method: {current_cooking_method}\n- excluded_keywords: {excluded_keywords}\n- aux_ingredients: {aux_ingredients}\n"

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
                        "aux_ingredients": {"type": "array", "items": {"type": "string"}}
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
            "aux_ingredients": aux_ingredients[:]
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
                matched_norm, score, _ = best_match
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

        # --- Final reply
        if not filters["main_ingredient"]:
            if ai_free_text:
                reply_text = ai_free_text
            else:
                reply_text = "Ποιο βασικό υλικό θα ήθελες να χρησιμοποιήσεις; 🙂"
        elif not filters["max_time"]:
            reply_text = "Πόσο χρόνο διαθέτεις για μαγείρεμα; 🙂"
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

    # ➤ Λίστα με fixed προτάσεις
    suggestion_messages = [
        "Τέλεια, τι λες για τα παρακάτω πιάτα;",
        "Τέλεια, πως σου φαίνονται τα παρακάτω;",
        "Τέλεια, τι θα έλεγες για:",
        "Τέλεια, ορίστε μερικές ιδέες:",
        "Τέλεια, ορίστε μερικά πιάτα που ταιριάζουν στις προτιμήσεις σου:"
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

        # =============== Branch 1: lexical match ==================
        if user_message:
            print("[DEBUG] ========== Branch 1 ==========")
            candidates = conn.execute("""
                SELECT recipes.*, 
                       CASE WHEN fav.recipe_id IS NOT NULL THEN 1 ELSE 0 END as is_favorite
                FROM recipes
                LEFT JOIN favorite_recipes fav 
                     ON fav.recipe_id = recipes.id AND fav.user_id = ?
            """, (session.get("user_id"),)).fetchall()

            matches = []
            for row in candidates:
                rid, raw_title, fav_flag = row["id"], row["title"], row["is_favorite"]
                score = fuzz.token_set_ratio(user_message, preprocess_title(raw_title))
                if score >= 80:
                    matches.append((row, score, fav_flag, raw_title))

            if matches:
                # Προτεραιότητα: 1) αγαπημένα, 2) score
                matches.sort(key=lambda x: (x[2], x[1]), reverse=True)

                print("[DEBUG] 📊 Branch1 match details:")
                for row, score, fav, raw_title in matches:
                    fav_mark = "🍀" if fav else "—"
                    print(f"    {raw_title} | score={score:.1f} | favorite={fav_mark}")

                matched_ids = [m[0]["id"] for m in matches]
                # Δεν χρειάζεται δεύτερο query!
                row_map = {row["id"]: row for row, _, _, _ in matches}

                # ➤ Φιλτράρουμε να μην ξαναπροταθούν ήδη προτεινόμενα πιάτα
                dishes_branch1 = [
                    row_map[mid] for mid in matched_ids
                    if mid in row_map and mid not in seen_ids and mid not in already_suggested
                ]

                print(f"[DEBUG] 🎯 Branch1 ordered return ({len(dishes_branch1)} dishes):",
                      [d["title"] for d in dishes_branch1])

                conn.close()
                step = data.get("step")
                print(f"[DEBUG] ✅ Final returned from Branch1 (step={step})")

                if step == 2:
                    # Επιστρέφουμε ΟΛΑ τα matches
                    session["suggested_dish_ids"] = already_suggested + [d["id"] for d in dishes_branch1]
                    return jsonify({
                        "message": random.choice(suggestion_messages),
                        "dishes": [dict(d) for d in dishes_branch1]
                    })

                # Κανονικά επιστρέφουμε max 3
                top_dishes = dishes_branch1[:3]
                session["suggested_dish_ids"] = already_suggested + [d["id"] for d in top_dishes]
                return jsonify({
                    "message": random.choice(suggestion_messages),
                    "dishes": [dict(d) for d in top_dishes]
                })
            else:
                print("[DEBUG] ❌ Branch1 no strong matches")

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
                "message": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια.. Θες να το ξαναπροσπαθήσουμε;; Πες μου με τι θα ήθελες να ξεκινήουμε!",
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
            "dishes": [dict(d) for d in final_dishes]
        })

    except Exception as e:
        print("[ERROR]", e)
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main"))
    else:
        return redirect(url_for("welcome"))

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

def get_user():    
    user_id = session.get("user_id")
    if not user_id:
        user_id = 1  # fallback μόνο για debug
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    members = conn.execute("SELECT * FROM family_members WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return user, members

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

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

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
                return redirect(url_for("main"))
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
            return redirect(url_for("main"))
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

@app.route("/welcome")
def welcome():     
    user, _ = get_user()
    hour = datetime.now().hour
    greeting = "Καλημέρα" if hour < 12 else "Καλησπέρα"
    day_idx = datetime.now().weekday()  # 0 = Δευτέρα
    day_name = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"][day_idx]

    # Βρες το τρέχον εβδομαδιαίο μενού του χρήστη
    week_start = (datetime.now() - timedelta(days=day_idx)).date()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.execute(
        "SELECT * FROM weekly_menu WHERE user_id=? AND week_start_date=? ORDER BY day_of_week ASC",
        (user["id"], str(week_start))
    )
    weekly_menu = c.fetchall()

    # Ορισμοί για σήμερα & αύριο
    today_menu = "-"
    today_menu_id = ""
    tomorrow_menu = "-"
    tomorrow_menu_id = ""

    if len(weekly_menu) == 7:
        recipe_today, recipe_tomorrow = None, None
        if weekly_menu[day_idx]["recipe_id"]:
            recipe_today = conn.execute("SELECT * FROM recipes WHERE id=?", (weekly_menu[day_idx]["recipe_id"],)).fetchone()
        if weekly_menu[(day_idx+1)%7]["recipe_id"]:
            recipe_tomorrow = conn.execute("SELECT * FROM recipes WHERE id=?", (weekly_menu[(day_idx+1)%7]["recipe_id"],)).fetchone()
        if recipe_today:
            t = recipe_today["total_time"] if recipe_today["total_time"] else "-"
            today_menu = f'{recipe_today["title"]} – χρόνος μαγειρέματος: {t}′'
            today_menu_id = recipe_today["id"]   # <--- Σωστά περνάμε το ID
        if recipe_tomorrow:
            t = recipe_tomorrow["total_time"] if recipe_tomorrow["total_time"] else "-"
            tomorrow_menu = f'{recipe_tomorrow["title"]} – χρόνος μαγειρέματος: {t}′'
            tomorrow_menu_id = recipe_tomorrow["id"]

    conn.close()
    
    return render_template(
        "welcome.html",
        greeting=greeting,
        user_name=user["first_name"],
        day_name=day_name,
        today_menu=today_menu,
        today_menu_id=today_menu_id,
        tomorrow_menu=tomorrow_menu,
        tomorrow_menu_id=tomorrow_menu_id,
    )

@app.route("/main")
@login_required
def main():
    clear_suggestions()
    return render_template("main.html")

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
    SELECT r.chef, r.main_dish_tag, r.total_time, r.method
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
        if r["main_dish_tag"]:
            categories.add(r["main_dish_tag"])
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


def strip_tonos(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn').lower()

@app.route("/api/favorites")
@login_required
def api_favorites():
    user, _ = get_user()
    user_id = user["id"]

    # Query params
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 4))
    method = request.args.get("method", "").strip()
    category = request.args.get("category", "").strip()
    chef = request.args.get("chef", "").strip()
    time_limit = request.args.get("max_time", "").strip()
    search = request.args.get("search", "").strip()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    base_query = """
    SELECT r.id, r.title, r.chef, r.prep_time, r.cook_time, r.url,
           r.main_dish_tag, r.total_time, r.created_by, r.parent_id,
           r.method, r.tags, r.ingredients, r.instructions
    FROM favorite_recipes f
    JOIN recipes r ON r.id = f.recipe_id
    WHERE f.user_id = ?
    """
    filters = [user_id]
    conditions = []

    if method:
        conditions.append("r.method = ?")
        filters.append(method)

    if category:
        conditions.append("r.main_dish_tag = ?")
        filters.append(category)

    if chef:
        conditions.append("r.chef = ?")
        filters.append(chef)

    if time_limit:
        try:
            time_limit = int(time_limit)
            conditions.append("r.total_time <= ?")
            filters.append(time_limit)
        except ValueError:
            pass

    if conditions:
        base_query += " AND " + " AND ".join(conditions)

    base_query += " ORDER BY f.rowid ASC"

    rows = conn.execute(base_query, filters).fetchall()
    conn.close()

    def row_to_dict(row):
        return {
            "id": row["id"],
            "title": row["title"],
            "chef": row["chef"],
            "prep_time": row["prep_time"],
            "cook_time": row["cook_time"],
            "total_time": row["total_time"],
            "url": row["url"],
            "main_dish_tag": row["main_dish_tag"],
            "created_by": row["created_by"],
            "method": row["method"],
            "tags": row["tags"],
            "ingredients": row["ingredients"],
            "instructions": row["instructions"]
        }

    all_recipes = [row_to_dict(r) for r in rows]

    # ✅ Fuzzy Search
    if search:
        search_clean = strip_tonos(search)
        
        def match(recipe):
            fields = [
                recipe["title"] or "",
                recipe["tags"] or "",
                recipe["main_dish_tag"] or ""
            ]
            for f in fields:
                target = strip_tonos(f)
                score = fuzz.partial_ratio(search_clean, target)
                if score > 85:  # κατώφλι fuzzy matching
                    return True
            return False
       
        all_recipes = [r for r in all_recipes if match(r)]

    total_count = len(all_recipes)
    start = (page - 1) * per_page
    end = start + per_page

    return jsonify({
        "recipes": all_recipes[start:end],
        "page": page,
        "total_pages": (total_count + per_page - 1) // per_page
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
            return jsonify({"success": True, "status": "removed", "first_time": False})
        else:
            # Προσθήκη αγαπημένης
            conn.execute(
                "INSERT INTO favorite_recipes (user_id, recipe_id) VALUES (?, ?)",
                (user_id, recipe_id)
            )

            # Έλεγχος για εγγραφή onboarding
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM onboarding_progress WHERE user_id = ? AND page = ?",
                (user_id, "favorites")
            )
            exists = cursor.fetchone()
            first_time = not exists

            if first_time:
                cursor.execute(
                    "INSERT INTO onboarding_progress (user_id, page, step, completed) VALUES (?, ?, ?, ?)",
                    (user_id, "favorites", 0, 0)
                )

            conn.commit()
            conn.close()

            return jsonify({
                "success": True,
                "status": "added",
                "first_time": first_time
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

@app.route("/profile")
@login_required
def profile():
    user, members = get_user()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    # Φέρε τους weekly_goals του χρήστη
    goals = conn.execute(
        "SELECT * FROM weekly_goals WHERE user_id=? ORDER BY id",
        (user["id"],)
    ).fetchall()

    # Κατηγορίες διαθέσιμες για στόχους
    categories = [
        'Κόκκινο κρέας', 'Ψάρι', 'Όσπρια', 'Λαδερά', 'Ζυμαρικά', 'Πουλερικά', 'Σαλάτα', 'Delivery'
    ]
    comparisons = ['τουλάχιστον', 'το πολύ']

    # Βρες όλους τους chef που έχουν πάνω από 1 συνταγή
    chefs = conn.execute("""
        SELECT chef, COUNT(*) as cnt
        FROM recipes
        WHERE chef IS NOT NULL AND chef != ''
        GROUP BY chef
        HAVING cnt > 1
        ORDER BY chef COLLATE NOCASE
    """).fetchall()
    chef_options = [r["chef"] for r in chefs]
    chef_options = sorted(set(chef_options), key=lambda x: x.lower())
    if "Κανένας" not in chef_options:
        chef_options = ["Κανένας"] + chef_options  # Βάλε πάντα πρώτο το "Κανένας"

    conn.close()

    return render_template(
        "profile_view.html",
        profile=user,
        members=members,
        weekly_goals=goals,
        categories=categories,
        comparisons=comparisons,
        all_allergs=get_all_allergens(),    
        chef_options=chef_options,
    )


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


