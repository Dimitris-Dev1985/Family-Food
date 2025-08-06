// ========== MENU ONBOARDING MINIMAL/ROBUST ==========

// LocalStorage helpers

function isMenuOnboardingDone() {
  return window.menuOnboardingServer.completed === true;
}

function getMenuOnboardingStep() {
  return Number(window.menuOnboardingServer.step || 0);
}

function setMenuOnboardingStep(step) {
  window.menuOnboardingServer.step = step;
  fetch("/api/onboarding_update_step", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ page: "menu", step })
  });
}

function setMenuOnboardingDone() {
  window.menuOnboardingServer.completed = true;
  document.body.classList.remove('menu-onboarding-active');

  fetch("/api/onboarding_mark_completed", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ page: "menu" })
  });
}

function resetMenuOnboarding() {
  localStorage.setItem('menu_onboarding_done', '0');
  localStorage.setItem('menu_onboarding_step', '0');
}

// Tooltips
const menuTooltips = [
  {
    selector: '#createMenuBtn',
    placement: 'bottom',
    arrow: 'up',
    html: `Πάτα εδώ για να δημιουργήσεις το πρώτο σου εβδομαδιαίο πρόγραμμα!`
  },
  {
    selector: '.recipe-card',
    placement: 'bottom',
    arrow: 'up',
    html: `
      Κάνοντας click σε ένα πιάτο εμφανίζεται η συνταγή του!
      <button class="btn btn-primary btn-sm" id="close-menu-tooltip2">Κατάλαβα!</button>
    `
  },
  {
    selector: '.fa-heart',
    placement: 'bottom',
    arrow: 'up',
    html: `
      Πρόσθεσε τη συνταγή στα Αγαπημένα σου πατώντας την καρδούλα!
      <button class="btn btn-primary btn-sm" id="close-menu-tooltip3">Κατάλαβα!</button>
    `
  },
  {
    selector: '.drag-handle',
    placement: 'bottom',
    arrow: 'up',
    html: `
      Σείρε αν θες ένα πιάτο από μια μέρα σε μια άλλη!
      <button class="btn btn-primary btn-sm" id="close-menu-tooltip4">Κατάλαβα!</button>
    `
  },
  {
    selector: '.btn-outline-primary',
    placement: 'top',
    arrow: 'down',
    html: `
      Πάτα το edit για να επιλέξεις το πιάτο της αρεσκείας σου για αυτή τη μέρα!
      <button class="btn btn-primary btn-sm" id="close-menu-tooltip5">Κατάλαβα!</button>
    `
  },
  {
    selector: '.fa-bullseye',
    placement: 'top',
    arrow: 'down',
    html: `
      Δες κατά πόσο το μενού εκπληρώνει τους διατροφικούς σου στόχους!
      <button class="btn btn-primary btn-sm" id="close-menu-tooltip6">Κατάλαβα!</button>
    `
  },
  {
    selector: null, // Δεν χρειάζεται anchor
    placement: 'center',
    arrow: null,
    html: `
      <div style="text-align: center;">
        <p style="font-size: 1.1rem; font-size: 20px; font-weight: bold;">Αυτό ήταν! Καλή εξερεύνηση!</p>
        <button class="btn btn-sm btn-success" id="close-menu-tooltip7">Φύγαμε!</button>
      </div>
    `
  }
];

// Εμφάνιση/Απόκρυψη
function showMenuTooltip(idx) {
  removeMenuTooltips();
  setMenuOnboardingStep(idx);

  const t = menuTooltips[idx];
  const target = t.selector ? document.querySelector(t.selector) : null;

  const tip = document.createElement('div');
  tip.className = 'menu-onboarding-tip';
  tip.innerHTML = t.html;
  tip.style.position = "absolute";
  tip.style.zIndex = "1001";
  tip.style.width = "auto";
  document.body.appendChild(tip);

  if (t.placement === 'center') {
    tip.style.left = (window.innerWidth / 2 - tip.offsetWidth / 2) + "px";
    tip.style.top = (window.innerHeight / 2 - tip.offsetHeight / 2 + window.scrollY) + "px";
    return;
  }

  if (!target) return;

  const rect = target.getBoundingClientRect();
  const scrollTop = window.scrollY;
  const tipWidth = tip.offsetWidth;
  const tipHeight = tip.offsetHeight;

  tip.style.left = (window.innerWidth / 2 - tipWidth / 2) + "px";

  if (t.placement === 'top') {
    tip.style.top = (scrollTop + rect.top - tipHeight - 12) + "px";
  } else {
    tip.style.top = (scrollTop + rect.bottom + 12) + "px";
  }

  if (t.arrow) {
    const arrow = document.createElement('div');
    arrow.className = t.arrow === 'down' ? 'onboard-arrow-down' : 'onboard-arrow-up';
    arrow.style.position = 'absolute';
    tip.appendChild(arrow);

    const tipRect = tip.getBoundingClientRect();
    const arrowWidth = arrow.offsetWidth;
    const targetCenterX = rect.left + rect.width / 2;
    let arrowLeft = targetCenterX - tipRect.left - arrowWidth / 2;
    arrowLeft = Math.max(8, Math.min(tipWidth - arrowWidth - 8, arrowLeft));
    arrow.style.left = arrowLeft + "px";

    if (t.arrow === 'down') {
      arrow.style.top = (tipHeight/2 + 24) + "px";
    } else {
      arrow.style.top = "-10px";
    }
  }
}

function removeMenuTooltips() {
  document.querySelectorAll('.menu-onboarding-tip').forEach(e => e.remove());
}

// Triggers

document.addEventListener('click', function(e) {
  if (!isMenuOnboardingDone()) {
    const step = getMenuOnboardingStep();

    if (step === 0 && e.target.closest('#createMenuBtn')) {
      removeMenuTooltips();
      setMenuOnboardingStep(1);
    }

    else if (step === 1 && e.target.id === 'close-menu-tooltip2') {
      removeMenuTooltips();
      setMenuOnboardingStep(2);
      showMenuTooltip(2);
    }

    else if (step === 2 && e.target.id === 'close-menu-tooltip3') {
      removeMenuTooltips();
      setMenuOnboardingStep(3);
      showMenuTooltip(3);
    }

    else if (step === 3 && e.target.id === 'close-menu-tooltip4') {
      removeMenuTooltips();
      setMenuOnboardingStep(4);
      showMenuTooltip(4);
    }

    else if (step === 4 && e.target.id === 'close-menu-tooltip5') {
      removeMenuTooltips();
      setMenuOnboardingStep(5);

      if (window.hasWeeklyGoals === true || window.hasWeeklyGoals === 'true') {
        showMenuTooltip(5);
      } else {
        setMenuOnboardingStep(6);
        showMenuTooltip(6); // τελικό κεντρικό tooltip
      }
    }

    else if (step === 5 && e.target.id === 'close-menu-tooltip6') {
      removeMenuTooltips();
      setMenuOnboardingStep(6);
      showMenuTooltip(6); // τελικό κεντρικό tooltip
    }

    else if (step === 6 && e.target.id === 'close-menu-tooltip7') {
      removeMenuTooltips();
      setMenuOnboardingDone();
    }
  }
});

// Modal hook
(function() {
  const origModal = bootstrap.Modal.prototype.hide;
  bootstrap.Modal.prototype.hide = function() {
    const isTargetModal = this._element && this._element.id === "menuCreatedModal";
    const isStep1 = (getMenuOnboardingStep() === 1 && !isMenuOnboardingDone());
    origModal.apply(this, arguments);
    setTimeout(function() {
      if (isTargetModal && isStep1) {
        showMenuTooltip(1);
      }
    }, 200);
  };
})();

function startMenuOnboarding() {
  if (!window.menuOnboardingServer.initialized) return;

  if (!isMenuOnboardingDone()) {
    document.body.classList.add('menu-onboarding-active');
    const step = getMenuOnboardingStep();

    if (step === 0) {
      showMenuTooltip(0);
    } else if (step === 1) {
      const modalEl = document.getElementById('menuCreatedModal');
      if (modalEl && !modalEl.classList.contains('show')) {
        showMenuTooltip(1);
      }
    } else if (step >= 2 && step <= 6) {
      if (step === 5 && !(window.hasWeeklyGoals === true || window.hasWeeklyGoals === 'true')) {
        setMenuOnboardingStep(6);
        showMenuTooltip(6);
      } else {
        showMenuTooltip(step);
      }
    }
  }
}
