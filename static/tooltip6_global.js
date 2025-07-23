
function shouldShowTooltip6() {
  const notShown = localStorage.getItem("onboarding_step6_shown") !== "1";
  const notDone = localStorage.getItem("onboarding_done") !== "1";
  for (let i = 1; i <= 5; i++) {
    if (!localStorage.getItem(`onboarding_step${i}_shown`)) return false;
  }
  return notShown && notDone;
}



window.addEventListener("DOMContentLoaded", function () {
  if (!shouldShowTooltip6()) return;

  const tooltip6 = document.getElementById("onboardingTooltip6");
  const menuLink = document.querySelector('nav.navbar.fixed-bottom a[href="/menu"]');

  if (tooltip6 && menuLink) {
    // Fixed position bottom center
    tooltip6.style.position = "absolute";
    tooltip6.style.left = "100px";
    tooltip6.style.bottom = "70px";
    tooltip6.style.transform = "translateX(-50%)";
    tooltip6.style.display = "block";
    tooltip6.style.visibility = "visible";

    menuLink.addEventListener("click", () => {
      localStorage.setItem("onboarding_step6_shown", "1");
      localStorage.setItem("onboarding_done", "1");
      tooltip6.style.display = "none";
      fetch("/api/onboarding_complete", { method: "POST" });
    });
  }
});
