from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash, get_flashed_messages
import sqlite3, unicodedata, random
from rapidfuzz import fuzz
from datetime import datetime, timedelta
from jinja2 import pass_context
from functools import wraps
from werkzeug.security import generate_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask_mail import Mail, Message

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
default_minutes = 60

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

@app.route("/")
def home():
    return redirect("/login")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()
        first_name = request.form.get("first_name", "").strip()
        family_name = request.form.get("family_name", "").strip()

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

        # Προσθήκη νέου χρήστη
        conn.execute("""
            INSERT INTO users (email, password, first_name, family_name)
            VALUES (?, ?, ?, ?)
        """, (email, password, first_name, family_name))
        conn.commit()

        # Ανάκτηση του νέου id
        user_id = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"]
        conn.close()

        session["user_id"] = user_id
        return redirect(url_for("welcome"))

    return render_template("signup.html")

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped

from werkzeug.security import check_password_hash

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if not get_flashed_messages():
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
                return redirect(url_for("welcome"))
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
            return redirect(url_for("main"))
        else:
            flash("Λανθασμένος κωδικός!", "danger")
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

@app.route("/install")
def install():
    return render_template("install.html")

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
def main():
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

    # Cooking methods options
    COOKING_METHODS = ['Φούρνος','Κατσαρόλα','Χύτρα','Τηγάνι','Σχάρα','Air-fryer']

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
    time_limit = request.args.get("time", "").strip()
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
                if score > 80:  # κατώφλι fuzzy matching
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
@login_required
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


@app.route('/ai_suggest_dish', methods=['POST'])
def ai_suggest_dish():
    data = request.get_json()
    step = data.get('step', 1)
    filters = data.get('filters', {})
    user, family = get_user()
    user = dict(user)  # 👈 αυτό προσθέτει τα fields ως dict

    # STEP 1: Χρόνος
    if step == 1:
        return jsonify({
            "question": "Πόσο χρόνο μπορείς να διαθέσεις σήμερα για μαγείρεμα;",
            "step": 2,
            "filters": filters
        })

    # STEP 2: Υλικό
    if step == 2:
        time_limit = int(data.get('answer', 120))
        filters['max_time'] = round(time_limit * 1.10)

        if not filters.get('ingredient_hint_shown'):
            filters['ingredient_hint_shown'] = True
            question_text = "Προτιμάς κάποιο συγκεκριμένο υλικό; (π.χ. κοτόπουλο, ψάρι, ζυμαρικά, μοσχάρι, λαχανικά, ή άφησέ το κενό)"
        else:
            question_text = "Προτιμάς κάποιο συγκεκριμένο υλικό;"

        return jsonify({
            "question": question_text,
            "step": 3,
            "filters": filters
        })

    # STEP 3: Πρόταση
    if step == 3:
        user_input = data.get('answer', '').strip()
        search_ingredient = remove_tonos(user_input)

        # Αλλεργίες
        allergy_set = set()
        family = [dict(m) for m in family]
        for member in family:
            raw_allergies = member.get("allergies", "")
            if raw_allergies:
                entries = [a.strip() for a in raw_allergies.split(',') if a.strip()]
                allergy_set.update(entries)  # αφήνουμε με τόνους – θα γίνουν remove στο SQL
        print(allergy_set)          

        # Προτιμήσεις
        method_prefs = []
        if user.get("cooking_method"):
            method_prefs = [m.strip() for m in user["cooking_method"].split(',')]
        print(method_prefs)    
        chef_pref = user["chef"].strip() if user.get("chef") else ""
        print(chef_pref)
        
        user_id = user["id"]
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        conn.create_function("remove_tonos", 1, remove_tonos)

        # Αγαπημένα του χρήστη
        fav_rows = conn.execute("SELECT recipe_id FROM favorite_recipes WHERE user_id = ?", (user_id,)).fetchall()
        fav_ids = [row["recipe_id"] for row in fav_rows]
        print(f"[AI DEBUG] Αγαπημένα του χρήστη: {fav_ids}")

        # Συνθήκες
        q = "SELECT * FROM recipes WHERE 1=1"
        params = []

        if 'max_time' in filters:
            q += " AND total_time<=?"
            params.append(filters['max_time'])

        for allergen in allergy_set:
            q += " AND remove_tonos(tags) NOT LIKE ? AND remove_tonos(ingredients) NOT LIKE ? AND remove_tonos(allergens) NOT LIKE ?"
            s = f"%{remove_tonos(allergen)}%"
            params.extend([s, s, s])

        if search_ingredient:
            q += " AND (remove_tonos(ingredients) LIKE ? OR remove_tonos(tags) LIKE ?)"
            s = f"%{search_ingredient}%"
            params.extend([s, s])
            
        missing = session.get('missing_ingredients', [])
        print(f"[AI DEBUG] missing: {missing}")
        for miss in missing:
            s = f"%{remove_tonos(miss.strip().lower())}%"
            q += " AND remove_tonos(ingredients) NOT LIKE ? AND remove_tonos(main_dish_tag) NOT LIKE ?"
            params.extend([s, s])

        # Προτεραιότητες
        q += " ORDER BY "
        if method_prefs:
            method_order = "CASE "
            for i, m in enumerate(method_prefs):
                method_order += f"WHEN method LIKE '%{m}%' THEN {i} "
            method_order += "ELSE 99 END,"
            q += method_order
        if chef_pref:
            q += f"CASE WHEN chef LIKE '%{chef_pref}%' THEN 0 ELSE 1 END, "
        q += "RANDOM()"
        print("Query preview:", q, "with params:", params)
        recipes = conn.execute(q, params).fetchall()
        conn.close()
        

        # Αποφυγή επαναλήψεων
        prev_ids = session.get('suggested_dish_ids', [])
        print(f"[AI DEBUG] Προηγούμενα IDs που έχουν προταθεί: {prev_ids}")
        
        filtered_recipes = [r for r in recipes if r['id'] not in prev_ids]
        print(f"[AI DEBUG] filtered_recipes: {[r['id'] for r in filtered_recipes]}")

        if not filtered_recipes:
            print("[AI DEBUG] Όλα τα διαθέσιμα πιάτα έχουν ήδη προταθεί.")
            return jsonify({
                "question": "Δυστυχώς δεν έχουμε άλλα πιάτα να προτείνουμε με αυτά τα κριτήρια! Θες να το ξαναπροσπαθήσουμε;",
                "step": 0,
                "dishes": [],
                "filters": filters
            })

        # Διαχωρισμός
        fav_recipes = [r for r in filtered_recipes if r["id"] in fav_ids]
        non_fav_recipes = [r for r in filtered_recipes if r["id"] not in fav_ids]

        print(f"[AI DEBUG] Αγαπημένα διαθέσιμα: {[r['id'] for r in fav_recipes]}")
        print(f"[AI DEBUG] Μη αγαπημένα διαθέσιμα: {[r['id'] for r in non_fav_recipes]}")

        # Συνένωση όλων, με προτεραιότητα αγαπημένα
        all_recipes = sorted(filtered_recipes, key=lambda r: 0 if r["id"] in fav_ids else 1)
        
        print(f"[AI DEBUG] All recipes: {[r['id'] for r in all_recipes]}")
        
        # Πάρε τα πρώτα 3
        dishes = []
        for r in all_recipes[:3]:
            dishes.append({
                "id": r["id"],
                "title": r["title"],
                "total_time": r["total_time"],
                "ingredients": r["ingredients"],
                "link": r["url"],
                "favorite": r["id"] in fav_ids
            })

        

        # Ενημέρωση session
        session['suggested_dish_ids'] = prev_ids + [r["id"] for r in dishes]

        print(f"[AI DEBUG] Προστέθηκαν νέα IDs: {[r['id'] for r in filtered_recipes[:3]]}")


        return jsonify({
            "question": "Τι λες για τα παρακάτω πιάτα;",
            "step": 0,
            "dishes": dishes,
            "filters": filters
        })

@app.route('/clear_suggestions', methods=['POST'])
def clear_suggestions():
    session.pop('suggested_dish_ids', None)
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


