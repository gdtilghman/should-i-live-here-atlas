"use strict";

// Plain-language definitions for less common words on the page.
// A defined word gets a dotted underline; clicking it opens a small popup.
// The popup closes on a click elsewhere, on Escape, or when the pointer moves
// far away. Definitions follow docs/glossary.md.
(() => {
  const TERMS = [
    { id: "concern-score", label: "Concern score", pattern: /\bconcern scores?\b/i,
      text: "Your My priorities result for a county, from 0 to 100. It combines your inputs and weights. A lower score means less of what you want to avoid." },
    { id: "weight", label: "Weight", pattern: /\bweights?\b/i,
      text: "How much an input counts in the concern score. All weights together make 100%." },
    { id: "hard-limit", label: "Hard limit", pattern: /\bhard limits?\b/i,
      text: "A rule you set. It removes counties with a value above or below your number." },
    { id: "extreme-value", label: "Extreme value", pattern: /\bextreme values?\b/i,
      text: "A value far above most counties. The map shows it in purple. It is not an error." },
    { id: "likely-range", label: "Likely range", pattern: /\blikely ranges?\b/i,
      text: "The range that probably holds the true value. With 95%, the true value is in this range 95 times in 100." },
    { id: "margin-of-error", label: "Margin of error", pattern: /\bmargins? of error\b/i,
      text: "How far a survey estimate can be from the true value. The true value is probably within this amount above or below it." },
    { id: "age", label: "Adjusted for age", pattern: /\b(?:adjusted for age|age adjustment)\b/i,
      text: "A calculation that removes the effect of age. It lets a county with many older people compare fairly with a younger county." },
    { id: "model-estimate", label: "Model estimate", pattern: /\bmodel estimates?\b/i,
      text: "A number that a computer model calculates. People did not count it directly, so it can be wrong for one county." },
    { id: "estimate", label: "Estimate", pattern: /(?<!\bmodel )\bestimates?\b/i,
      text: "A number calculated from a survey of some people, not a count of everyone. It has some uncertainty." },
    { id: "suppressed", label: "Suppressed", pattern: /\bsuppressed\b/i,
      text: "The source hides this value. Often the numbers are too small to report safely or reliably." },
    { id: "not-applicable", label: "Not applicable", pattern: /\bnot applicable\b/i,
      text: "FEMA does not model this hazard for the county, because the county is not exposed to it. For example, hurricanes and inland counties." },
    { id: "unavailable", label: "Unavailable", pattern: /\bunavailable\b/i,
      text: "The site has no value for this county. County details give the reason. An unavailable value never counts as zero." },
    { id: "excluded", label: "Excluded", pattern: /\bexcluded\b/i,
      text: "Your hard limit removed this county from the comparison." },
    { id: "input", label: "Input", pattern: /\binputs?\b/i,
      text: "A measure you add to My priorities. Each input has a weight." },
    { id: "national-scale", label: "National scale", pattern: /\bnational scale\b/i,
      text: "The map uses the same colors for the whole country. A state view keeps these colors, so you can compare states fairly." },
    { id: "national-rank", label: "National rank", pattern: /\bnational ranks?\b/i,
      text: "Where the county stands among all U.S. counties, from 0 to 100. A county at 90 is higher than about 90% of counties." },
    { id: "shortage-area", label: "Shortage area", pattern: /\bshortage areas?\b/i,
      text: "An area the federal government lists as short of primary care providers. An area gets on the list only after an application." },
    { id: "priority-score", label: "Priority score", pattern: /\bpriority score\b/i,
      text: "A federal score for how much an area needs more primary care providers. A higher score means greater need." },
    { id: "health-violation", label: "Health-based violation", pattern: /\bhealth-based (?:Safe Drinking Water Act )?violations?\b/i,
      text: "A break of a drinking water rule that protects health. Examples are too much of a contaminant or a missed treatment step." },
    { id: "community-water", label: "Community water system", pattern: /\bcommunity water systems?\b/i,
      text: "A public water system that serves the same people all year, such as a town or city system. Private wells are not included." },
    { id: "declaration", label: "Major-disaster declaration", pattern: /\bmajor-disaster declarations?\b/i,
      text: "A formal decision by the President that a disaster needs federal help. It is a record of help, not a measure of damage." },
  ];

  const CONTAINERS = [".legend-block", "#fact-panel", ".method-section", "#ranking-report", ".controls-panel", ".data-dock"];
  const SKIP = "button, a, select, option, label, input, textarea, th, td, summary, h1, h2, h3, svg, script, style, .term, [data-no-terms]";
  const CLOSE_DISTANCE = 90;
  const byId = new Map(TERMS.map(term => [term.id, term]));

  const popup = document.createElement("div");
  popup.id = "term-popup";
  popup.className = "term-popup";
  popup.setAttribute("role", "dialog");
  popup.setAttribute("aria-modal", "false");
  popup.hidden = true;
  const popupTitle = document.createElement("p");
  popupTitle.className = "term-popup__title";
  popupTitle.id = "term-popup-title";
  const popupText = document.createElement("p");
  popupText.className = "term-popup__text";
  popup.setAttribute("aria-labelledby", popupTitle.id);
  popup.append(popupTitle, popupText);
  let openTerm = null;

  function decorate(container) {
    const done = new Set([...container.querySelectorAll(".term")].map(node => node.dataset.term));
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode: node => node.nodeValue.trim() && !node.parentElement?.closest(SKIP)
        ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
    });
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      let current = node;
      while (current?.nodeValue) {
        // Wrap the earliest term in this text; longer terms win a tie.
        let best = null;
        for (const term of TERMS) {
          if (done.has(term.id)) continue;
          const found = term.pattern.exec(current.nodeValue);
          if (found && (!best || found.index < best.match.index
            || (found.index === best.match.index && found[0].length > best.match[0].length))) {
            best = { term, match: found };
          }
        }
        if (!best) break;
        const { term, match } = best;
        const after = current.splitText(match.index);
        const rest = after.splitText(match[0].length);
        const button = document.createElement("button");
        button.type = "button";
        button.className = "term";
        button.dataset.term = term.id;
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-controls", popup.id);
        button.textContent = after.nodeValue;
        after.replaceWith(button);
        done.add(term.id);
        current = rest;
      }
    }
  }

  let queued = false;
  function decorateAll() {
    queued = false;
    for (const selector of CONTAINERS) {
      document.querySelectorAll(selector).forEach(decorate);
    }
    if (openTerm && !openTerm.isConnected) close(false);
  }
  function queue() {
    if (queued) return;
    queued = true;
    setTimeout(decorateAll, 0);
  }

  function place() {
    if (!openTerm) return;
    const margin = 12;
    const anchor = openTerm.getBoundingClientRect();
    const box = popup.getBoundingClientRect();
    let top = anchor.bottom + 8;
    if (top + box.height > window.innerHeight - margin && anchor.top - box.height - 8 > margin) {
      top = anchor.top - box.height - 8;
    }
    const left = Math.min(Math.max(margin, anchor.left), document.documentElement.clientWidth - box.width - margin);
    popup.style.top = `${Math.max(margin, top)}px`;
    popup.style.left = `${Math.max(margin, left)}px`;
  }

  function open(button) {
    if (openTerm === button) return close(true);
    if (openTerm) close(false);
    const term = byId.get(button.dataset.term);
    if (!term) return;
    popupTitle.textContent = term.label;
    popupText.textContent = term.text;
    popup.hidden = false;
    openTerm = button;
    button.setAttribute("aria-expanded", "true");
    place();
  }

  function close(returnFocus) {
    if (!openTerm) return;
    const button = openTerm;
    openTerm = null;
    popup.hidden = true;
    button.setAttribute("aria-expanded", "false");
    if (returnFocus && button.isConnected) button.focus();
  }

  function distance(x, y, rect) {
    const dx = Math.max(rect.left - x, 0, x - rect.right);
    const dy = Math.max(rect.top - y, 0, y - rect.bottom);
    return Math.hypot(dx, dy);
  }

  document.addEventListener("click", event => {
    const button = event.target.closest?.(".term");
    if (button) {
      event.preventDefault();
      open(button);
    } else if (openTerm && !popup.contains(event.target)) {
      close(false);
    }
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && openTerm) close(true);
  });
  document.addEventListener("pointermove", event => {
    if (!openTerm || event.pointerType !== "mouse") return;
    const near = Math.min(
      distance(event.clientX, event.clientY, openTerm.getBoundingClientRect()),
      distance(event.clientX, event.clientY, popup.getBoundingClientRect())
    );
    if (near > CLOSE_DISTANCE) close(false);
  });
  window.addEventListener("scroll", place, { passive: true, capture: true });
  window.addEventListener("resize", () => close(false));

  function start() {
    document.body.append(popup);
    new MutationObserver(queue).observe(document.body, { childList: true, subtree: true, characterData: true });
    queue();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
