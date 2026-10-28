"use strict";

// Fills the "Data sources" list from data/sources.json, so anyone can check
// where each topic's values come from.
(() => {
  const list = document.querySelector("#data-sources-list");
  if (!list) return;

  function link(href, text) {
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = `${text} ↗`;
    return a;
  }

  function line(className, label, text) {
    const p = document.createElement("p");
    p.className = className;
    if (label) {
      const strong = document.createElement("strong");
      strong.textContent = `${label} `;
      p.append(strong);
    }
    p.append(text);
    return p;
  }

  function render(data) {
    list.replaceChildren();
    for (const entry of data.sources) {
      const item = document.createElement("li");
      item.className = "data-sources__item";
      item.dataset.family = entry.family;
      const topic = document.createElement("p");
      topic.className = "data-sources__topic";
      topic.textContent = entry.topic;
      const links = document.createElement("p");
      links.className = "data-sources__links";
      links.append(link(entry.page, "Source page"));
      if (entry.data && entry.data !== entry.page) links.append(" · ", link(entry.data, "Data"));
      if (entry.terms) links.append(" · ", link(entry.terms, "Terms of use"));
      item.append(
        topic,
        line("data-sources__name", "", entry.source),
        line("data-sources__date", "Retrieved:", entry.retrieved),
        links,
        line("data-sources__cite", "Cite as:", entry.citation),
      );
      list.append(item);
    }
  }

  fetch("./data/sources.json")
    .then(response => {
      if (!response.ok) throw new Error(String(response.status));
      return response.json();
    })
    .then(render)
    .catch(() => {
      list.replaceChildren();
      const item = document.createElement("li");
      item.textContent = "The source list did not load. The details for each measure still link to its source.";
      list.append(item);
    });
})();
