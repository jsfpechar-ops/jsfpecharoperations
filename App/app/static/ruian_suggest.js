/* 0835: address suggestions for the police-address fields (shared with the setup wizard).
   Contract: an input[data-ruian-suggest] inside a form that holds inputs named
   addr_street, addr_house_no, addr_orient_no, addr_zip, addr_obec, addr_obec_cast, addr_okres.
   A suggestion only fills the values; the host still edits and submits them.
   Without JS, or when the endpoint returns [] or fails, the plain fields work. */
(function () {
  'use strict';

  var FIELDS = ['addr_street', 'addr_house_no', 'addr_orient_no', 'addr_zip', 'addr_obec', 'addr_obec_cast', 'addr_okres'];
  var MIN_CHARS = 3;
  var DEBOUNCE_MS = 250;
  var MAX_ITEMS = 6;
  var ENDPOINT = '/apartments/ruian-suggest';

  function attach(input) {
    var form = input.form;
    if (!form || input.getAttribute('data-ruian-attached') === '1') return;
    input.setAttribute('data-ruian-attached', '1');

    var targets = {};
    FIELDS.forEach(function (name) {
      var el = form.querySelector('input[name="' + name + '"]');
      if (el) targets[name] = el;
    });

    var listId = (input.id || 'addr-street') + '-suggest';
    var list = document.createElement('ul');
    list.id = listId;
    list.className = 'ruian-suggest';
    list.setAttribute('role', 'listbox');
    list.hidden = true;
    input.insertAdjacentElement('afterend', list);
    // Visible status so a slow or empty lookup is never silent (the service can take a few seconds).
    var status = document.createElement('p');
    status.className = 'hint ruian-status';
    status.id = listId + '-status';
    status.setAttribute('role', 'status');
    status.hidden = true;
    list.insertAdjacentElement('afterend', status);
    function say(text) {
      status.textContent = text || '';
      status.hidden = !text;
    }
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-controls', listId);

    var items = [];
    var active = -1;
    var timer = null;
    var controller = null;
    var seq = 0;

    function cancel() {
      seq += 1;
      clearTimeout(timer);
      if (controller && controller.abort) controller.abort();
      controller = null;
    }

    function close() {
      say('');
      list.hidden = true;
      list.textContent = '';
      items = [];
      active = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function hide() {
      list.hidden = true;
      active = -1;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
    }

    function setActive(i) {
      active = i;
      var opts = list.querySelectorAll('[role="option"]');
      for (var k = 0; k < opts.length; k++) {
        opts[k].setAttribute('aria-selected', k === i ? 'true' : 'false');
      }
      if (i >= 0) input.setAttribute('aria-activedescendant', listId + '-' + i);
      else input.removeAttribute('aria-activedescendant');
    }

    function pick(i) {
      var item = items[i];
      if (!item || !item.fields) return;
      var fields = item.fields;
      FIELDS.forEach(function (name) {
        var el = targets[name];
        if (!el || !Object.prototype.hasOwnProperty.call(fields, name)) return;
        var v = fields[name];
        el.value = v == null ? '' : String(v);
      });
      cancel();
      close();
      var order = FIELDS.filter(function (n) { return targets[n]; });
      var next = null;
      for (var k = order.indexOf(input.name) + 1; k < order.length; k++) {
        if (!targets[order[k]].value) { next = targets[order[k]]; break; }
      }
      if (next) next.focus();
    }

    function render(list_items) {
      items = list_items;
      list.textContent = '';
      items.forEach(function (item, i) {
        var li = document.createElement('li');
        li.id = listId + '-' + i;
        li.setAttribute('role', 'option');
        li.setAttribute('aria-selected', 'false');
        li.textContent = item.label;
        li.addEventListener('mousedown', function (e) { e.preventDefault(); });
        li.addEventListener('click', function () { pick(i); });
        list.appendChild(li);
      });
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      setActive(-1);
    }

    function noMatch() {
      close();
      say(input.getAttribute('data-ruian-none'));
    }

    function load(q) {
      var mine = seq;
      say(input.getAttribute('data-ruian-loading'));
      controller = typeof AbortController === 'function' ? new AbortController() : null;
      var opts = { credentials: 'same-origin', headers: { Accept: 'application/json' } };
      if (controller) opts.signal = controller.signal;
      fetch(ENDPOINT + '?q=' + encodeURIComponent(q), opts)
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (data) {
          if (mine !== seq) return;
          if (!Array.isArray(data)) return noMatch();
          var valid = data.filter(function (x) {
            return x && typeof x.label === 'string' && x.fields && typeof x.fields === 'object';
          }).slice(0, MAX_ITEMS);
          if (!valid.length) return noMatch();
          say('');
          render(valid);
        })
        .catch(function () { if (mine === seq) noMatch(); });
    }

    input.addEventListener('input', function () {
      cancel();
      close();
      var q = input.value.trim();
      if (q.length < MIN_CHARS) return;
      timer = setTimeout(function () { load(q); }, DEBOUNCE_MS);
    });

    input.addEventListener('keydown', function (e) {
      var open = !list.hidden && items.length > 0;
      if (!open) {
        if (e.key === 'ArrowDown' && items.length > 0) {
          e.preventDefault();
          list.hidden = false;
          input.setAttribute('aria-expanded', 'true');
          setActive(0);
        }
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive(active < items.length - 1 ? active + 1 : 0);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive(active > 0 ? active - 1 : items.length - 1);
      } else if (e.key === 'Enter' && active >= 0) {
        e.preventDefault();
        pick(active);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        cancel();
        hide();
      }
    });

    input.addEventListener('blur', function () { cancel(); close(); });
  }

  function init() {
    var inputs = document.querySelectorAll('input[data-ruian-suggest]');
    for (var i = 0; i < inputs.length; i++) attach(inputs[i]);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
