// --- Chat History: Minimal & Reliable ---

// 1. Αρχικοποίηση chat όταν φορτώνει η σελίδα
window.addEventListener('DOMContentLoaded', function() {
  // Αν υπάρχει ιστορικό στο storage, κάνε restore (και άνοιξε το chatbox αυτόματα!)
  if (sessionStorage.getItem('chatHistory')) {
    restoreChatHistory();
    restoreChatControls();
    showChatbox(true); // το true για auto-open, χωρίς να αλλάξει το κουμπί
  }
});

// 2. Εμφάνιση του chatbox και διαχείριση κουμπιού
function showChatbox(auto = false) {
  document.getElementById('chatbox-section').style.display = '';

  const lead = document.getElementById('welcomeLead');
  if (lead) lead.style.display = 'none';

  const btn = document.getElementById('startChatBtn');
  btn.innerText = 'Restart Chat!';
  btn.onclick = function () {
    aiChatFilters = {};
    restartChat();
  };
  btn.disabled = false;

  if (!sessionStorage.getItem('chatHistory') && !auto) {
    clearChatHistory();
    clearChatControls();
    addChatLine('assistant', '<b>' + window.dayName + '</b>' + ' σήμερα, τι θα μαγειρέψουμε;');
    showMainChoices();
  }

  if (typeof showMainChoices === "function" && !document.querySelector('#chatbox #choicesRow')) {
    showMainChoices();
  }

  setTimeout(() => {
    const chatbox = document.getElementById('chatbox');
    chatbox.scrollTop = chatbox.scrollHeight;
    window.scrollTo({ top: document.getElementById('chatbox-section').offsetTop - 20, behavior: 'smooth' });
  }, 80);
}

// 3. Πρόσθεση chat line (και αυτόματο save)
function addChatLine(who, text) {
  const chatbox = document.getElementById('chatbox');
  const classes = { assistant: 'chat-assistant', user: 'chat-user' };
  const icons = { assistant: '👩‍🍳', user: '🙋‍♂️' };

  document.querySelectorAll('#chatbox .ai-ok-btn').forEach(btn => {
    btn.disabled = true;
    btn.classList.add('disabled');
  });

  let line = '';
  if (who === 'controls') {
    line = text;
  } else {
    const whoClass = classes[who] || '';
    const icon = icons[who] || '';
    line = `<div class="chat-line"><span class="${whoClass}">${icon}</span> ${text}</div>`;
  }
  chatbox.insertAdjacentHTML('beforeend', line);
  chatbox.scrollTop = chatbox.scrollHeight;
  saveChatHistory();
}

// 4. Save/Restore/Clear chat history
function saveChatHistory() {
  sessionStorage.setItem('chatHistory', document.getElementById('chatbox').innerHTML);
}
function restoreChatHistory() {
  let hist = sessionStorage.getItem('chatHistory');
  if (hist) {
    document.getElementById('chatbox').innerHTML = hist;
    document.getElementById('chatbox').scrollTop = document.getElementById('chatbox').scrollHeight;
  }
}
function clearChatHistory() {
  sessionStorage.removeItem('chatHistory');
  document.getElementById('chatbox').innerHTML = '';
}

// 5. Chat controls (αν έχεις buttons στο κάτω μέρος)
function setChatControls(html) {
  document.getElementById('ai-chat-controls').innerHTML = html;
  sessionStorage.setItem('chatControls', html);
}
function restoreChatControls() {
  let controls = sessionStorage.getItem('chatControls');
  if (controls) document.getElementById('ai-chat-controls').innerHTML = controls;
}
function clearChatControls() {
  document.getElementById('ai-chat-controls').innerHTML = "";
  sessionStorage.removeItem('chatControls');
}

// 6. Restart Chat
function restartChat() {
  if (!confirm("Θέλεις να διαγράψεις το ιστορικό συνομιλίας;")) return;

  fetch('/clear_suggestions', { method: 'POST' })
    .then(() => {
      clearChatHistory();
      clearChatControls();
      addChatLine('assistant', '<b>' + window.dayName + '</b>' + ' σήμερα, τι θα μαγειρέψουμε;');
      showMainChoices();
    });
}
