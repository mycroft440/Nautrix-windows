// Copyright 2021 The Chromium Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import 'chrome://resources/cr_components/most_visited/most_visited.js';

import {assert} from 'chrome://resources/js/assert.js';
import {skColorToRgba} from 'chrome://resources/js/color_utils.js';

import {BrowserProxy} from './browser_proxy.js';

// NAUTRIX_NEW_TAB_PAGE_BEGIN
type NautrixSearchEngine = 'google'|'bing'|'duckduckgo'|'brave';

const SEARCH_ENGINE_STORAGE_KEY = 'nautrix.searchEngine';
const SEARCH_ENGINES: Record<NautrixSearchEngine, {
  label: string,
  searchUrl: string,
}> = {
  google: {label: 'Google', searchUrl: 'https://www.google.com/search?q='},
  bing: {label: 'Bing', searchUrl: 'https://www.bing.com/search?q='},
  duckduckgo: {label: 'DuckDuckGo', searchUrl: 'https://duckduckgo.com/?q='},
  brave: {label: 'Brave Search', searchUrl: 'https://search.brave.com/search?q='},
};

function isSearchEngine(value: string|null): value is NautrixSearchEngine {
  return value !== null &&
      Object.prototype.hasOwnProperty.call(SEARCH_ENGINES, value);
}

function loadSearchEngine(): NautrixSearchEngine {
  try {
    const saved = window.localStorage.getItem(SEARCH_ENGINE_STORAGE_KEY);
    if (isSearchEngine(saved)) {
      return saved;
    }
  } catch {
    // The local page still works if profile storage is unavailable.
  }
  return 'google';
}

const searchForm = document.querySelector<HTMLFormElement>('#search-form');
const searchInput = document.querySelector<HTMLInputElement>('#search-input');
const searchEngine =
    document.querySelector<HTMLSelectElement>('#search-engine');
assert(searchForm);
assert(searchInput);
assert(searchEngine);

let selectedSearchEngine = loadSearchEngine();
searchEngine.value = selectedSearchEngine;

function updateSearchPlaceholder() {
  const engine = SEARCH_ENGINES[selectedSearchEngine];
  searchInput.placeholder = `Pesquisar no ${engine.label} ou digitar uma busca`;
}

searchEngine.addEventListener('change', () => {
  const value = searchEngine.value;
  if (!isSearchEngine(value)) {
    searchEngine.value = selectedSearchEngine;
    return;
  }

  selectedSearchEngine = value;
  try {
    window.localStorage.setItem(
        SEARCH_ENGINE_STORAGE_KEY, selectedSearchEngine);
  } catch {
    // Keep the current page selection even without profile storage.
  }
  updateSearchPlaceholder();
  searchInput.focus();
});

searchForm.addEventListener('submit', event => {
  event.preventDefault();
  const query = searchInput.value.trim();
  if (!query) {
    searchInput.focus();
    return;
  }

  const searchUrl = SEARCH_ENGINES[selectedSearchEngine].searchUrl;
  window.location.assign(searchUrl + encodeURIComponent(query));
});

updateSearchPlaceholder();
// NAUTRIX_NEW_TAB_PAGE_END

const {callbackRouter, handler} = BrowserProxy.getInstance();

callbackRouter.setTheme.addListener(theme => {
  const html = document.documentElement;
  html.toggleAttribute('has-custom-background', theme.hasCustomBackground);
  const style = html.style;
  style.backgroundColor = theme.colorBackground;
  const backgroundImage = `image-set(
      url(chrome://theme/IDR_THEME_NTP_BACKGROUND?${theme.id}) 1x,
      url(chrome://theme/IDR_THEME_NTP_BACKGROUND@2x?${theme.id}) 2x)`;
  style.backgroundImage = theme.hasCustomBackground ? backgroundImage : '';
  style.backgroundRepeat = theme.backgroundTiling;
  style.backgroundPosition = theme.backgroundPosition;
  style.setProperty('--ntp-theme-text-color', skColorToRgba(theme.textColor));

  const mostVisitedElement = document.querySelector('cr-most-visited');
  assert(mostVisitedElement);
  mostVisitedElement.theme = theme.mostVisited;
});
handler.updateTheme();
