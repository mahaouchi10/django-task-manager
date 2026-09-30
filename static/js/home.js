(function () {
  "use strict";

  var navbar = document.querySelector(".navbar");
  var menu = document.querySelector(".navbar .nav-links");
  var hamburger = document.querySelector(".navbar .hamburger");

  // Hamburger menu toggle
  function toggleMenu(open) {
    if (!menu) return;
    menu.classList.toggle("open", open);
    if (hamburger) hamburger.setAttribute("aria-expanded", String(open));
  }

  if (hamburger) {
    hamburger.addEventListener("click", function () {
      var expanded = hamburger.getAttribute("aria-expanded") === "true";
      toggleMenu(!expanded);
    });
  }

  // Close mobile menu when a link is clicked
  if (menu) {
    menu.addEventListener("click", function (e) {
      if (e.target.tagName === "A") toggleMenu(false);
    });
  }

  // Navbar blur + background on scroll
  function onScroll() {
    if (!navbar) return;
    if (window.scrollY > 8) {
      navbar.classList.add("scrolled");
    } else {
      navbar.classList.remove("scrolled");
    }
  }
  window.addEventListener("scroll", onScroll);

  // Scroll reveal animations
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in-view");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
  );

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".animate").forEach(function (el) {
      observer.observe(el);
    });

    // Logout confirmation modal
    var logoutForm = document.querySelector('#logout-confirm-form');
    var trigger = document.querySelector('#nav-links button.logout-btn');
    var modal = document.querySelector('#logout-modal');

    if (!logoutForm || !trigger || !modal) return;

    var cancelBtn = modal.querySelector('#logout-modal-cancel');
    var closeBtn = modal.querySelector('#logout-modal-close');

    function openModal() {
      modal.classList.add('active');
      modal.setAttribute('aria-hidden', 'false');
      cancelBtn.focus();
    }
    function closeModal() {
      modal.classList.remove('active');
      modal.setAttribute('aria-hidden', 'true');
      trigger.focus();
    }

    trigger.addEventListener("click", function (e) {
      e.preventDefault();
      openModal();
    });

    cancelBtn.addEventListener("click", closeModal);
    closeBtn.addEventListener("click", closeModal);

    modal.addEventListener("click", function (e) {
      if (e.target === modal) closeModal();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains('active')) closeModal();
    });
  });
})();
