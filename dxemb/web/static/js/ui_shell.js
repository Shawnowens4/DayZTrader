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
    var images = document.querySelectorAll("img[data-fallback-src]");
    for (var i = 0; i < images.length; i += 1) {
      var img = images[i];
      if (img instanceof HTMLImageElement && !img.getAttribute("src")) {
        applyImageFallback(img);
      }
    }
  });
})();
