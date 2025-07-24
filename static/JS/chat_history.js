// --- Chat History: Minimal & Reliable ---

// 1. Αρχικοποίηση chat όταν φορτώνει η σελίδα
window.addEventListener('DOMContentLoaded', function() {
  // Αν υπάρχει ιστορικό στο storage, κάνε restore (και άνοιξε το chatbox αυτόματα!)
  if (localStorage.getItem('chatHistory')) {
    restoreChatHistory();
    restoreChatControls();
    showChatbox(true); // το true για auto-open, χωρίς να αλλάξει το κουμπί
  }
});

// 2. Εμφάνιση του chatbox και διαχείριση κουμπιού
function showChatbox(auto = false) {
  document.getElementById('chatbox-section').style.display = '';
  let lead = document.getElementById('welcomeLead');
  if (lead) lead.style.display = 'none';

  let btn = document.getElementById('startChatBtn');
  btn.innerText = 'Restart Chat!';
  btn.onclick = restartChat;
  btn.disabled = false;

  // Αν το ανοίγεις μόνος σου (όχι auto από ιστορικό), βάλε το αρχικό μήνυμα αν δεν υπάρχει ιστορικό
  if (!localStorage.getItem('chatHistory') && !auto) {
    clearChatHistory();
    clearChatControls();
    addChatLine('assistant', window.dayName +' σήμερα, τι θα μαγειρέψουμε;');
    showMainChoices();
  }

  // Scroll στην τελευταία γραμμή
  setTimeout(() => {
    document.getElementById('chatbox').scrollTop = document.getElementById('chatbox').scrollHeight;
    window.scrollTo({top: document.getElementById('chatbox-section').offsetTop - 20, behavior:'smooth'});
  }, 80);
}

// 3. Πρόσθεση chat line (και αυτόματο save)
function addChatLine(who, text) {
  let chatbox = document.getElementById('chatbox');
  let whoClass = (who === 'assistant') ? 'chat-assistant' : (who === 'user') ? 'chat-user' : '';
  let icon = (who === 'assistant') ? "👩‍🍳" : (who === 'user') ? "🙋‍♂️" : "";
  let line = '';
  if (who === 'controls') {
    line = text;
  } else {
    line = `<div class="chat-line"><span class="${whoClass}">${icon}</span> ${text}</div>`;
  }
  chatbox.insertAdjacentHTML('beforeend', line);
  chatbox.scrollTop = chatbox.scrollHeight;
  saveChatHistory();
}

// 4. Save/Restore/Clear chat history
function saveChatHistory() {
  localStorage.setItem('chatHistory', document.getElementById('chatbox').innerHTML);
}
function restoreChatHistory() {
  let hist = localStorage.getItem('chatHistory');
  if (hist) {
    document.getElementById('chatbox').innerHTML = hist;
    document.getElementById('chatbox').scrollTop = document.getElementById('chatbox').scrollHeight;
  }
}
function clearChatHistory() {
  localStorage.removeItem('chatHistory');
  document.getElementById('chatbox').innerHTML = '';
}

// 5. Chat controls (αν έχεις buttons στο κάτω μέρος)
function setChatControls(html) {
  document.getElementById('ai-chat-controls').innerHTML = html;
  localStorage.setItem('chatControls', html);
}
function restoreChatControls() {
  let controls = localStorage.getItem('chatControls');
  if (controls) document.getElementById('ai-chat-controls').innerHTML = controls;
}
function clearChatControls() {
  document.getElementById('ai-chat-controls').innerHTML = "";
  localStorage.removeItem('chatControls');
}

// 6. Restart Chat
function restartChat() {
  if (!confirm("Θέλεις να διαγράψεις το ιστορικό συνομιλίας;")) return;
  clearChatHistory();
  clearChatControls();
  addChatLine('assistant', window.dayName +' σήμερα, τι θα μαγειρέψουμε;');
  showMainChoices();
}

