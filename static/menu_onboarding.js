// ========== MENU ONBOARDING MINIMAL/ROBUST ==========

// LocalStorage helpers
function isMenuOnboardingDone() {
  return localStorage.getItem('menu_ondording_done') === '1';
}
function setMenuOnboardingDone() {
  localStorage.setItem('menu_ondording_done', '1');
}
function resetMenuOnboarding() {
  localStorage.setItem('menu_ondording_done', '0');
  localStorage.setItem('menu_onboarding_step', '0');
}
function getMenuOnboardingStep() {
  return Number(localStorage.getItem('menu_onboarding_step') || '0');
}
function setMenuOnboardingStep(step) {
  localStorage.setItem('menu_onboarding_step', String(step));
}

// Βάλε ΕΣΥ το selector και το html κάθε tooltip όπως θες!
const menuTooltips = [
  {
    selector: '#createMenuBtn',  // Το anchor element για το 1ο tooltip
	placement: 'bottom',
    arrow: 'up',
    html: `
            Πάτα εδώ για να δημιουργήσεις το πρώτο σου εβδομαδιαίο πρόγραμμα!
         `
  },
  {
    selector: '.recipe-card',
    placement: 'bottom',
    arrow: 'up',
	html: `
        Κάνοντας click σε ένα πιάτο εμφανίζεται η συνταγή του!
		  <button class="btn btn-primary btn-sm" id="close-menu-tooltip2" style="display: inline-block; margin-left: 8px; padding: 2px 2px;">
			Κατάλαβα!
		  </button>
    `
  },
  {
    selector: '.fa-heart',
    placement: 'bottom',
    arrow: 'up',
	html: `
        Πρόσθεσε τη συνταγή στα Αγαπημένα σου πατώντας την καρδούλα!
		  <button class="btn btn-primary btn-sm" id="close-menu-tooltip3" style="display: inline-block; margin-left: 8px; padding: 2px 2px;">
			Κατάλαβα!
		  </button>
    `
  },
  {
    selector: '.drag-handle',
    placement: 'bottom',
    arrow: 'up',
	html: `
	  Σείρε αν θες ένα πιάτο από μια μέρα σε μια άλλη!
		  <button class="btn btn-primary btn-sm" id="close-menu-tooltip4" style="display: inline-block; margin-left: 8px; padding: 2px 2px;">
			Κατάλαβα!
		  </button>
    `
  },
  {
    selector: '.btn-outline-primary',
    placement: 'bottom',
    arrow: 'up',
	html: `
        Πάτα το edit για να επιλεξεις το πιάτο της αρεσκείας σου για αυτή τη μέρα!
		  <button class="btn btn-primary btn-sm" id="close-menu-tooltip5" style="display: inline-block; margin-left: 8px; padding: 2px 2px;">
			Κατάλαβα!
		  </button>
    `
  },
  {
    selector: '.fa-bullseye',
    placement: 'top',
    arrow: 'down',
	html: `
        Δες κατά πόσο το μενού εκπληρώνει τους διατροφικούς σου στόχους!
		  <button class="btn btn-primary btn-sm" id="close-menu-tooltip6" style="display: inline-block; margin-left: 8px; padding: 2px 2px;">
			Κατάλαβα!
		  </button>
    `
  }
];

// Εμφάνιση/απόκρυψη
function showMenuTooltip(idx) {
  removeMenuTooltips();
  setMenuOnboardingStep(idx);

  const t = menuTooltips[idx];
  const target = document.querySelector(t.selector);
  if (!target) return;

  // Tooltip
  const tip = document.createElement('div');
  tip.className = 'menu-onboarding-tip';
  tip.innerHTML = t.html;
  tip.style.position = "absolute";
  tip.style.zIndex = "1001";
  document.body.appendChild(tip);


  // Placement
  const rect = target.getBoundingClientRect();
  const scrollTop = window.scrollY;
  const tipWidth = tip.offsetWidth;
  const tipHeight = tip.offsetHeight;


  // Οριζόντια ΚΕΝΤΡΟ
  tip.style.left = (window.innerWidth / 2 - tipWidth / 2) + "px";
  // Πάνω ή κάτω από το target
  if (t.placement === 'top') {
    tip.style.top = (scrollTop + rect.top - tipHeight - 12) + "px";
  } else {
    tip.style.top = (scrollTop + rect.bottom + 12) + "px";
  }

  // Arrow
  const arrow = document.createElement('div');
  arrow.className = t.arrow === 'down' ? 'onboard-arrow-down' : 'onboard-arrow-up';
  arrow.style.position = 'absolute';
  tip.appendChild(arrow);

  // Υπολογισμός θέσης arrow
  const tipRect = tip.getBoundingClientRect();
  const arrowWidth = arrow.offsetWidth;
  const targetCenterX = rect.left + rect.width / 2;
  let arrowLeft = targetCenterX - tipRect.left - arrowWidth / 2;
  // Clamp για να μην βγει το arrow εκτός
  arrowLeft = Math.max(8, Math.min(tipWidth - arrowWidth - 8, arrowLeft));
  arrow.style.left = arrowLeft + "px";

  // Arrow top/bottom δυναμικά!
	if (t.arrow === 'down') {
	  arrow.style.top = (tipHeight/2 + 9) + "px";
	} else {
	  arrow.style.top = "-9px";
	}

}


function removeMenuTooltips() {
  document.querySelectorAll('.menu-onboarding-tip').forEach(e=>e.remove());
}

// ========== Hooks / Triggers ==========

// 1. Εμφανίζει το tooltip1 στο load (αν δεν έχει ολοκληρωθεί)
window.addEventListener('DOMContentLoaded', function() {
  if (!isMenuOnboardingDone() && getMenuOnboardingStep() === 0) {
    showMenuTooltip(0);
  }
});

// 2. Tooltip1 εξαφανίζεται με click στο "Δημιουργία νέου Εβδομαδιαίου Μενού"
document.addEventListener('click', function(e) {
  if (!isMenuOnboardingDone() && getMenuOnboardingStep() === 0) {
    const t = menuTooltips[0];
    const btn = document.querySelector(t.selector);
    if (btn && (e.target === btn || btn.contains(e.target))) {
      removeMenuTooltips();
      setMenuOnboardingStep(1);
      // Tooltip2 εμφανίζεται ΜΟΝΟ όταν κλείσει το modal, όχι εδώ!
    }
  }
});

// 3. Tooltip2 εμφανίζεται όταν ΚΛΕΙΣΕΙ το menuCreatedModal
(function() {
  const origModal = bootstrap.Modal.prototype.hide;
  bootstrap.Modal.prototype.hide = function() {
    const isTargetModal = this._element && this._element.id === "menuCreatedModal";
    const isStep1 = (getMenuOnboardingStep() === 1 && !isMenuOnboardingDone());
    origModal.apply(this, arguments);
    setTimeout(function() {
      if (isTargetModal && isStep1) {
        showMenuTooltip(1); // Tooltip2
      }
    }, 200);
  };
})();

// Tooltip2-6: κάθε Κατάλαβα πάει στο επόμενο tooltip
document.addEventListener('click', function(e) {
  if (!isMenuOnboardingDone()) {
    const step = getMenuOnboardingStep();
    // Tooltip2
    if (step === 1 && e.target && e.target.id === 'close-menu-tooltip2') {
      removeMenuTooltips();
      setMenuOnboardingStep(2);
      showMenuTooltip(2);
    }
    // Tooltip3
    if (step === 2 && e.target && e.target.id === 'close-menu-tooltip3') {
      removeMenuTooltips();
      setMenuOnboardingStep(3);
      showMenuTooltip(3);
    }
    // Tooltip4
    if (step === 3 && e.target && e.target.id === 'close-menu-tooltip4') {
      removeMenuTooltips();
      setMenuOnboardingStep(4);
      showMenuTooltip(4);
    }
    // Tooltip5
    if (step === 4 && e.target && e.target.id === 'close-menu-tooltip5') {
      removeMenuTooltips();
      setMenuOnboardingStep(5);
      showMenuTooltip(5);
    }
    // Tooltip6 - τέλος!
    if (step === 5 && e.target && e.target.id === 'close-menu-tooltip6') {
      removeMenuTooltips();
      setMenuOnboardingDone();
    }
  }
});
