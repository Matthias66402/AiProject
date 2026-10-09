// Zentrale Frontend-Einstellungen.

// Einträge pro Seite, mit denen die großen Listen (Stellenangebote,
// Stellenanbieter) starten; der Nutzer kann den Wert dort über
// "Einträge pro Seite" ändern.
export const DEFAULT_PER_PAGE = 10

// Einträge pro Seite in den Seitenspalten der Detailseiten (z. B. Stellen
// eines Stellenanbieters) - dort gibt es keine Auswahl.
export const SIDE_PANEL_PER_PAGE = 5

// Das Backend akzeptiert Werte von 1 bis zur größten Option aus
// JOBS_PER_PAGE_OPTIONS (api/jobs.py, 100) bzw. CUSTOMERS_PER_PAGE_OPTIONS
// (api/customers.py, 50); größere Werte ersetzt es durch seinen Standardwert.
// DEFAULT_PER_PAGE sollte zudem eine der Optionen sein, sonst zeigt das
// Auswahlfeld "Einträge pro Seite" keinen passenden Eintrag an.

// Auswahl "Entfernung" in der Stellensuche (Rolle 'user'): Wert für den
// URL-/API-Parameter distance und Beschriftung. Die Kilometer dazu stehen in
// DISTANCE_KM in api/jobs.py; 'relocate' filtert nicht (Voreinstellung).
export const DISTANCE_OPTIONS = [
    ['near', 'Wohnortnähe (bis 10 km)'],
    ['25', 'bis 25 km'],
    ['50', 'bis 50 km'],
    ['100', 'bis 100 km'],
    ['relocate', 'umzugsbereit'],
]
export const DEFAULT_DISTANCE = 'relocate'
