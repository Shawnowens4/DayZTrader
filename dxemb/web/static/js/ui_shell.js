(function () {
  "use strict";

  function applyImageFallback(img) {
    if (!img) {
      return;
    }
    var fallbackSrc = img.getAttribute("data-fallback-src");
    if (!fallbackSrc) {
      return;
    }
    if (img.dataset.fallbackApplied === "1") {
      return;
    }
    img.dataset.fallbackApplied = "1";
    img.src = fallbackSrc;
    img.classList.add("is-fallback-image");
  }

  document.addEventListener(
    "error",
    function (event) {
      var target = event.target;
      if (target instanceof HTMLImageElement && target.dataset.fallbackSrc) {
        applyImageFallback(target);
      }
    },
    true
  );

  document.addEventListener("DOMContentLoaded", function () {
    var currentPath = window.location.pathname;
    var navLinks = document.querySelectorAll(".shell-nav a");
    for (var navIndex = 0; navIndex < navLinks.length; navIndex += 1) {
      var navLink = navLinks[navIndex];
      var linkPath = new URL(navLink.href, window.location.origin).pathname;
      var isCurrent =
        linkPath === "/"
          ? currentPath === "/"
          : currentPath === linkPath || currentPath.indexOf(linkPath + "/") === 0;
      if (isCurrent) {
        navLink.setAttribute("aria-current", "page");
      }
    }

    var images = document.querySelectorAll("img[data-fallback-src]");
    for (var i = 0; i < images.length; i += 1) {
      var img = images[i];
      if (img instanceof HTMLImageElement && !img.getAttribute("src")) {
        applyImageFallback(img);
      }
    }

    var colorOptions = document.querySelectorAll("[data-vehicle-color]");
    var selectedColorName = document.getElementById("selected-color-name");
    var selectedVehiclePreview = document.getElementById("selected-vehicle-preview");
    var reviewStatus = document.getElementById("vehicle-review-status");
    for (var colorIndex = 0; colorIndex < colorOptions.length; colorIndex += 1) {
      colorOptions[colorIndex].addEventListener("click", function () {
        for (var optionIndex = 0; optionIndex < colorOptions.length; optionIndex += 1) {
          colorOptions[optionIndex].classList.remove("selected");
          colorOptions[optionIndex].setAttribute("aria-pressed", "false");
        }
        this.classList.add("selected");
        this.setAttribute("aria-pressed", "true");
        if (selectedColorName) {
          selectedColorName.textContent = this.getAttribute("data-vehicle-color") || "Standard";
        }
        if (selectedVehiclePreview) {
          selectedVehiclePreview.src =
            this.getAttribute("data-vehicle-color-image") || selectedVehiclePreview.src;
          selectedVehiclePreview.dataset.fallbackApplied = "0";
        }
        if (reviewStatus) {
          reviewStatus.textContent =
            "Selection updated for review. Nothing has been saved or delivered.";
        }
      });
    }
  });
})();
