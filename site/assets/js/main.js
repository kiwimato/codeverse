/* Codeverse — codeverse.nl
   Three small jobs: the mobile menu, the current year, and assembling the
   contact address at runtime so it never sits in the served HTML. */
(function () {
  'use strict';

  /* ---------- Mobile navigation ---------- */
  var toggle = document.getElementById('nav-toggle');
  var nav = document.getElementById('site-nav');

  if (toggle && nav) {
    toggle.addEventListener('click', function () {
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });

    // Tapping a link on mobile should close the menu behind you.
    nav.addEventListener('click', function (e) {
      if (e.target.tagName === 'A' && nav.classList.contains('open')) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', 'Open menu');
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('open')) {
        nav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        toggle.focus();
      }
    });
  }

  /* ---------- Footer year ---------- */
  var year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* ---------- Contact address ----------
     Stored base64-encoded and split in two, so neither the address nor a
     single decodable blob appears in the HTML or JS source. This stops the
     bulk of address-harvesting crawlers, which parse markup and never run
     JavaScript. It is deliberately NOT security — anyone determined can read
     this file. That is why the address below should be a disposable alias
     (see README.md), not a personal mailbox.

     To change the address:
       echo -n 'newalias'    | base64   ->  LOCAL
       echo -n 'example.com' | base64   ->  DOMAIN  */
  var LOCAL   = 'aGVsbG8=';           // "hello"
  var DOMAIN  = 'Y29kZXZlcnNlLm5s';   // "codeverse.nl"
  var SUBJECT = 'Enquiry via codeverse.nl';

  var slot = document.getElementById('email-slot');
  if (slot && window.atob) {
    var address = atob(LOCAL) + String.fromCharCode(64) + atob(DOMAIN);

    var link = document.createElement('a');
    link.className = 'btn btn-primary';
    link.href = 'mailto:' + address + '?subject=' + encodeURIComponent(SUBJECT);
    link.rel = 'nofollow';
    var label = document.createElement('span');
    label.className = 'email-address';
    label.textContent = address;
    link.appendChild(label);

    var copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'copy-btn';
    copy.textContent = 'Copy';
    copy.addEventListener('click', function () {
      var done = function () {
        copy.textContent = 'Copied';
        copy.setAttribute('data-copied', 'true');
        setTimeout(function () {
          copy.textContent = 'Copy';
          copy.removeAttribute('data-copied');
        }, 2000);
      };

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(address).then(done, function () {
          copy.textContent = address; // Clipboard refused: show it to select by hand.
        });
      } else {
        copy.textContent = address;
      }
    });

    slot.appendChild(link);
    slot.appendChild(copy);
  }
})();
