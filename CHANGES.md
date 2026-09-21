# Shelf – Änderungen in diesem Fork

Diese Datei ist die zentrale Übersicht für alle Anpassungen dieses Forks. Die
upstream [`README.md`](README.md) beschreibt weiterhin Shelf selbst; hier
stehen ausschließlich die zusätzlichen oder abweichenden Funktionen dieses
Forks.

## Spieleplattformen auf der Startseite

- Die Home-Seite zeigt für jede Plattform mit katalogisierten Videospielen
  eine eigene Kachel.
- Jede Kachel enthält den Plattformnamen, die Anzahl der Spiele und – sofern
  vorhanden – ihr Plattformlogo.
- Ein Klick öffnet die Browse-Ansicht bereits auf diese Plattform gefiltert.
- Die Zählung und Filterung verwendet die vorhandenen Plattform-Metadaten
  (`game_platforms` und `items.platform`), nicht duplizierte Tags. Es werden
  ausschließlich Videospiele berücksichtigt.

## Plattformfilter

- Browse besitzt einen Plattformfilter mit dynamischen Trefferzahlen.
- Der Filter lässt sich mit den übrigen Browse-Filtern kombinieren und
  berücksichtigt nur Videospiele.

## Plattformlogos

- Unter **Settings → Library → Platform Logos** lassen sich Plattform und
  Logo-Datei zuordnen.
- Ein Eintrag oder eine Änderung wird direkt mit **Save mapping** gespeichert;
  es gibt keinen zweiten globalen Speichern-Schritt.
- Die SVG-Auswahl ist auf Dateien aus `static/icons/svg` begrenzt. Eigene
  Zuordnungen überschreiben die eingebauten Standardvorschläge.
- Die Standardzuordnungen sind nur erste Vorschläge und können jederzeit in
  den Einstellungen geändert werden.

Die verwendeten monochromen Plattformlogos stammen aus
[HVR88/Monochrome-Gaming-Logos](https://github.com/HVR88/Monochrome-Gaming-Logos).
Bitte beachte die Lizenz und Hinweise dieses Projekts, wenn Logos verteilt oder
verändert werden.

## Lokale Entwicklung unter Windows/WSL

- `make dev` baut und startet die Docker-Entwicklungsinstanz unter
  `https://localhost:18889`.
- Die Docker-Compose-Konfiguration veröffentlicht den HTTPS-Port explizit,
  damit die Instanz auch aus einem Windows-Browser erreichbar ist.
- `make dev-local` startet einen lokalen Uvicorn-Entwicklungsserver mit Hot
  Reload unter `http://localhost:8000`.
