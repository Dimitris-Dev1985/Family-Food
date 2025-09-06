// 🌐 Cooking Assistant – localStorage Utilities

const StorageKeys = {
  MAX_TIME: "max_time",
  MAIN_INGREDIENT: "main_ingredient",
  METHOD_PREFS: "method_prefs",
  EXCLUDED: "excluded",
  AUX_INGREDIENTS: "aux_ingredients"   
};

// ➤ Ασφαλές setter
function setStorageItem(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.error(`[ERROR] ❌ Failed to save ${key}:`, e);
  }
}

// ➤ Ασφαλές getter
function getStorageItem(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (e) {
    console.warn(`[WARN] Failed to read ${key}, returning fallback.`);
    return fallback;
  }
}

// ➤ Ειδικές συναρτήσεις για κάθε μεταβλητή

function setMaxTime(minutes) {
  setStorageItem(StorageKeys.MAX_TIME, String(minutes));
}

function getMaxTime() {
  return getStorageItem(StorageKeys.MAX_TIME, "30"); // default 30 λεπτά
}

function setMainIngredient(ingredient) {
  setStorageItem(StorageKeys.MAIN_INGREDIENT, ingredient);
}

function getMainIngredient() {
  return getStorageItem(StorageKeys.MAIN_INGREDIENT, null);
}

function setMethodPrefs(methodsArray) {
  setStorageItem(StorageKeys.METHOD_PREFS, methodsArray);
}

function getMethodPrefs() {
  return getStorageItem(StorageKeys.METHOD_PREFS, [
    'Φούρνος', 'Κατσαρόλα', 'Χύτρα', 'Τηγάνι', 'Σχάρα', 'Air-fryer'
  ]);
}

function setExcluded(excludesArray) {
  setStorageItem(StorageKeys.EXCLUDED, excludesArray);
}

function getExcluded() {
  return getStorageItem(StorageKeys.EXCLUDED, []);
}

// ✅ Νέες συναρτήσεις για auxiliary ingredients
function setAuxIngredient(auxArray) {
  setStorageItem(StorageKeys.AUX_INGREDIENTS, auxArray);
}

function getAuxIngredient() {
  return getStorageItem(StorageKeys.AUX_INGREDIENTS, []);
}

// ➤ Clear All
function clearCookingFilters() {
  Object.values(StorageKeys).forEach(k => localStorage.removeItem(k));
  console.log("[DEBUG] 🧹 Cleared all cooking filters from localStorage");
}
