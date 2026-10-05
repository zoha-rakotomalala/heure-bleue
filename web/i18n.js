// heure bleue -- languages, place and units, shared by the three pages.
//
// Where a choice comes from, first match wins:
//   language  ?lang=xx  ->  this browser (localStorage)  ->  config.json "language"
//             ->  config.json "locale" prefix  ->  the browser's own language  ->  en
//   place     this browser (localStorage)  ->  config.json "city"
//   units     this browser (localStorage)  ->  config.json "units"  ->  celsius
// The wall's own panel (the ⚙ button) writes the browser choices. "Reset" clears them.
//
// Adding a language: one more entry in LANGS below. Every key must be present;
// a missing key falls back to English at runtime, so a partial entry still works.
(() => {
  const LANGS = {
    en: { name: "English",
      mood: "matched to the album cover",
      tip_theme: "Wall colour", tip_swap: "Another painting", tip_keep: "Keep this one", tip_kept: "Kept paintings", tip_next: "Next song", tip_prefs: "Language, place, units",
      st_loading: "loading the painting", st_museum: "the museum did not answer, trying another", st_choosing: "choosing another painting", st_reading: "reading the album cover", st_next: "next song", st_player: "the player did not answer",
      playing: "playing", paused: "paused", paused_rot: "paused · the wall rotates",
      sunset_in: "sunset in {n} min", blue_hour: "blue hour", set_at: "sun set at {t}", first_light_in: "first light in {n} min", blue_morning: "morning blue hour", rise_at: "risen at {t}",
      clear: "Clear sky", mostly_clear: "Mostly clear", partly: "Partly cloudy", overcast: "Overcast", fog: "Fog", rime: "Freezing fog", drizzle_l: "Light drizzle", drizzle: "Drizzle", drizzle_d: "Dense drizzle", fdrizzle: "Freezing drizzle", rain_l: "Light rain", rain: "Rain", rain_h: "Heavy rain", frain: "Freezing rain", snow_l: "Light snow", snow: "Snow", snow_h: "Heavy snow", showers: "Showers", showers_h: "Heavy showers", snow_showers: "Snow showers", storm: "Thunderstorm",
      language: "Language", place: "Place", search_city: "search a city", my_position: "use my position", locating: "locating…", not_found: "no place found", no_position: "position not available", units: "Units", reset: "reset to config.json", update: "new version {v} available",
      kept: "Kept", wall: "wall", stats: "stats", museum: "museum", order: "order", newest: "newest", oldest: "oldest", artist: "artist", all: "all", empty_kept: "Nothing kept yet. Press L on the wall.", open: "open", remove: "remove", song_tip: "playing when you kept this",
      since: "since {d}", empty_stats: "Nothing yet.", empty_stats_sub: "The wall writes one line each time the painting changes.", nothing_yet: "nothing yet",
      shown: "paintings shown", works: "different works", on_wall: "on the wall", skipped: "skipped", with_music: "with music",
      museums: "Museums", time_on_wall: "time on the wall", centuries: "Centuries", century: "{n}th century", painters: "Painters", most_on_wall: "most on the wall", most_shown: "Most shown", sec_skipped: "Skipped", skipped_sub: "the ones you moved past", music: "Music", music_sub: "artists behind the wall", songs: "Songs", pairings: "Pairings", pairings_sub: "music artist → painter matched most", of: "{a} of {b}", by_museum: "by museum", songs_hearts: "Songs behind the hearts", hours: "Hours", hours_sub: "when the wall is on", h: "h", min: "min",
    },
    fr: { name: "Français",
      mood: "accordé à la pochette de l’album",
      tip_theme: "Couleur du mur", tip_swap: "Un autre tableau", tip_keep: "Garder celui-ci", tip_kept: "Tableaux gardés", tip_next: "Chanson suivante", tip_prefs: "Langue, lieu, unités",
      st_loading: "chargement du tableau", st_museum: "le musée ne répond pas, on en essaie un autre", st_choosing: "choix d’un autre tableau", st_reading: "lecture de la pochette", st_next: "chanson suivante", st_player: "le lecteur ne répond pas",
      playing: "en cours", paused: "en pause", paused_rot: "en pause · le mur tourne",
      sunset_in: "coucher du soleil dans {n} min", blue_hour: "heure bleue", set_at: "soleil couché à {t}", first_light_in: "première lueur dans {n} min", blue_morning: "heure bleue du matin", rise_at: "levé à {t}",
      clear: "Ciel clair", mostly_clear: "Presque clair", partly: "Quelques nuages", overcast: "Couvert", fog: "Brouillard", rime: "Brouillard givrant", drizzle_l: "Bruine légère", drizzle: "Bruine", drizzle_d: "Bruine dense", fdrizzle: "Bruine verglaçante", rain_l: "Pluie légère", rain: "Pluie", rain_h: "Pluie forte", frain: "Pluie verglaçante", snow_l: "Neige légère", snow: "Neige", snow_h: "Neige forte", showers: "Averses", showers_h: "Averses fortes", snow_showers: "Averses de neige", storm: "Orage",
      language: "Langue", place: "Lieu", search_city: "chercher une ville", my_position: "utiliser ma position", locating: "localisation…", not_found: "aucun lieu trouvé", no_position: "position indisponible", units: "Unités", reset: "revenir à config.json", update: "nouvelle version {v} disponible",
      kept: "Gardés", wall: "mur", stats: "stats", museum: "musée", order: "ordre", newest: "récents", oldest: "anciens", artist: "artiste", all: "tous", empty_kept: "Rien de gardé pour l’instant. Appuyez sur L sur le mur.", open: "ouvrir", remove: "retirer", song_tip: "ce qui jouait quand vous l’avez gardé",
      since: "depuis le {d}", empty_stats: "Rien pour l’instant.", empty_stats_sub: "Le mur écrit une ligne à chaque changement de tableau.", nothing_yet: "rien pour l’instant",
      shown: "tableaux montrés", works: "œuvres différentes", on_wall: "sur le mur", skipped: "passés", with_music: "avec musique",
      museums: "Musées", time_on_wall: "temps sur le mur", centuries: "Siècles", century: "{n}e siècle", painters: "Peintres", most_on_wall: "les plus présents", most_shown: "Les plus montrés", sec_skipped: "Passés", skipped_sub: "ceux que vous avez sautés", music: "Musique", music_sub: "les artistes derrière le mur", songs: "Chansons", pairings: "Accords", pairings_sub: "artiste → peintre le plus souvent associé", of: "{a} sur {b}", by_museum: "par musée", songs_hearts: "Les chansons derrière les cœurs", hours: "Heures", hours_sub: "quand le mur est allumé", h: "h", min: "min",
    },
    nl: { name: "Nederlands",
      mood: "afgestemd op de albumhoes",
      tip_theme: "Muurkleur", tip_swap: "Een ander schilderij", tip_keep: "Deze bewaren", tip_kept: "Bewaarde schilderijen", tip_next: "Volgend nummer", tip_prefs: "Taal, plaats, eenheden",
      st_loading: "schilderij wordt geladen", st_museum: "het museum antwoordt niet, we proberen een ander", st_choosing: "een ander schilderij kiezen", st_reading: "de albumhoes lezen", st_next: "volgend nummer", st_player: "de speler antwoordt niet",
      playing: "speelt", paused: "gepauzeerd", paused_rot: "gepauzeerd · de muur wisselt",
      sunset_in: "zonsondergang over {n} min", blue_hour: "blauwe uur", set_at: "zon onder om {t}", first_light_in: "eerste licht over {n} min", blue_morning: "blauwe uur van de ochtend", rise_at: "opgekomen om {t}",
      clear: "Heldere hemel", mostly_clear: "Vrijwel helder", partly: "Half bewolkt", overcast: "Bewolkt", fog: "Mist", rime: "Aanvriezende mist", drizzle_l: "Lichte motregen", drizzle: "Motregen", drizzle_d: "Dichte motregen", fdrizzle: "IJzel (motregen)", rain_l: "Lichte regen", rain: "Regen", rain_h: "Zware regen", frain: "IJzel", snow_l: "Lichte sneeuw", snow: "Sneeuw", snow_h: "Zware sneeuw", showers: "Buien", showers_h: "Zware buien", snow_showers: "Sneeuwbuien", storm: "Onweer",
      language: "Taal", place: "Plaats", search_city: "zoek een stad", my_position: "mijn positie gebruiken", locating: "locatie bepalen…", not_found: "geen plaats gevonden", no_position: "positie niet beschikbaar", units: "Eenheden", reset: "terug naar config.json", update: "nieuwe versie {v} beschikbaar",
      kept: "Bewaard", wall: "muur", stats: "statistieken", museum: "museum", order: "volgorde", newest: "nieuwste", oldest: "oudste", artist: "kunstenaar", all: "alle", empty_kept: "Nog niets bewaard. Druk op L op de muur.", open: "openen", remove: "verwijderen", song_tip: "speelde toen je dit bewaarde",
      since: "sinds {d}", empty_stats: "Nog niets.", empty_stats_sub: "De muur schrijft een regel bij elke wissel van schilderij.", nothing_yet: "nog niets",
      shown: "schilderijen getoond", works: "verschillende werken", on_wall: "aan de muur", skipped: "overgeslagen", with_music: "met muziek",
      museums: "Musea", time_on_wall: "tijd aan de muur", centuries: "Eeuwen", century: "{n}e eeuw", painters: "Schilders", most_on_wall: "meest aan de muur", most_shown: "Meest getoond", sec_skipped: "Overgeslagen", skipped_sub: "die je voorbij liet gaan", music: "Muziek", music_sub: "de artiesten achter de muur", songs: "Nummers", pairings: "Paren", pairings_sub: "muzikant → vaakst gekoppelde schilder", of: "{a} van {b}", by_museum: "per museum", songs_hearts: "Nummers achter de hartjes", hours: "Uren", hours_sub: "wanneer de muur aan is", h: "u", min: "min",
    },
    de: { name: "Deutsch",
      mood: "auf das Albumcover abgestimmt",
      tip_theme: "Wandfarbe", tip_swap: "Ein anderes Gemälde", tip_keep: "Dieses behalten", tip_kept: "Behaltene Gemälde", tip_next: "Nächstes Lied", tip_prefs: "Sprache, Ort, Einheiten",
      st_loading: "Gemälde wird geladen", st_museum: "das Museum antwortet nicht, ein anderes wird versucht", st_choosing: "ein anderes Gemälde wird gewählt", st_reading: "das Albumcover wird gelesen", st_next: "nächstes Lied", st_player: "der Player antwortet nicht",
      playing: "läuft", paused: "pausiert", paused_rot: "pausiert · die Wand wechselt",
      sunset_in: "Sonnenuntergang in {n} Min", blue_hour: "blaue Stunde", set_at: "Sonne untergegangen um {t}", first_light_in: "erstes Licht in {n} Min", blue_morning: "blaue Stunde am Morgen", rise_at: "aufgegangen um {t}",
      clear: "Klarer Himmel", mostly_clear: "Überwiegend klar", partly: "Teils bewölkt", overcast: "Bedeckt", fog: "Nebel", rime: "Gefrierender Nebel", drizzle_l: "Leichter Sprühregen", drizzle: "Sprühregen", drizzle_d: "Dichter Sprühregen", fdrizzle: "Gefrierender Sprühregen", rain_l: "Leichter Regen", rain: "Regen", rain_h: "Starker Regen", frain: "Gefrierender Regen", snow_l: "Leichter Schnee", snow: "Schnee", snow_h: "Starker Schnee", showers: "Schauer", showers_h: "Starke Schauer", snow_showers: "Schneeschauer", storm: "Gewitter",
      language: "Sprache", place: "Ort", search_city: "Stadt suchen", my_position: "meinen Standort verwenden", locating: "Standort wird bestimmt…", not_found: "kein Ort gefunden", no_position: "Standort nicht verfügbar", units: "Einheiten", reset: "zurück zu config.json", update: "neue Version {v} verfügbar",
      kept: "Behalten", wall: "Wand", stats: "Statistik", museum: "Museum", order: "Reihenfolge", newest: "neueste", oldest: "älteste", artist: "Künstler", all: "alle", empty_kept: "Noch nichts behalten. Drücke L auf der Wand.", open: "öffnen", remove: "entfernen", song_tip: "lief, als du dieses behalten hast",
      since: "seit {d}", empty_stats: "Noch nichts.", empty_stats_sub: "Die Wand schreibt bei jedem Gemäldewechsel eine Zeile.", nothing_yet: "noch nichts",
      shown: "Gemälde gezeigt", works: "verschiedene Werke", on_wall: "an der Wand", skipped: "übersprungen", with_music: "mit Musik",
      museums: "Museen", time_on_wall: "Zeit an der Wand", centuries: "Jahrhunderte", century: "{n}. Jahrhundert", painters: "Maler", most_on_wall: "am längsten an der Wand", most_shown: "Am häufigsten gezeigt", sec_skipped: "Übersprungen", skipped_sub: "die du weitergeklickt hast", music: "Musik", music_sub: "die Künstler hinter der Wand", songs: "Lieder", pairings: "Paare", pairings_sub: "Musiker → am häufigsten zugeordneter Maler", of: "{a} von {b}", by_museum: "nach Museum", songs_hearts: "Lieder hinter den Herzen", hours: "Stunden", hours_sub: "wann die Wand an ist", h: "Std", min: "Min",
    },
    es: { name: "Español",
      mood: "a juego con la portada del álbum",
      tip_theme: "Color de la pared", tip_swap: "Otro cuadro", tip_keep: "Guardar este", tip_kept: "Cuadros guardados", tip_next: "Siguiente canción", tip_prefs: "Idioma, lugar, unidades",
      st_loading: "cargando el cuadro", st_museum: "el museo no responde, probamos otro", st_choosing: "eligiendo otro cuadro", st_reading: "leyendo la portada del álbum", st_next: "siguiente canción", st_player: "el reproductor no responde",
      playing: "sonando", paused: "en pausa", paused_rot: "en pausa · la pared rota",
      sunset_in: "puesta de sol en {n} min", blue_hour: "hora azul", set_at: "sol puesto a las {t}", first_light_in: "primera luz en {n} min", blue_morning: "hora azul de la mañana", rise_at: "salido a las {t}",
      clear: "Cielo despejado", mostly_clear: "Casi despejado", partly: "Parcialmente nublado", overcast: "Cubierto", fog: "Niebla", rime: "Niebla helada", drizzle_l: "Llovizna ligera", drizzle: "Llovizna", drizzle_d: "Llovizna densa", fdrizzle: "Llovizna helada", rain_l: "Lluvia ligera", rain: "Lluvia", rain_h: "Lluvia fuerte", frain: "Lluvia helada", snow_l: "Nieve ligera", snow: "Nieve", snow_h: "Nieve fuerte", showers: "Chubascos", showers_h: "Chubascos fuertes", snow_showers: "Chubascos de nieve", storm: "Tormenta",
      language: "Idioma", place: "Lugar", search_city: "buscar una ciudad", my_position: "usar mi posición", locating: "localizando…", not_found: "ningún lugar encontrado", no_position: "posición no disponible", units: "Unidades", reset: "volver a config.json", update: "nueva versión {v} disponible",
      kept: "Guardados", wall: "pared", stats: "estadísticas", museum: "museo", order: "orden", newest: "recientes", oldest: "antiguos", artist: "artista", all: "todos", empty_kept: "Nada guardado todavía. Pulsa L en la pared.", open: "abrir", remove: "quitar", song_tip: "sonaba cuando lo guardaste",
      since: "desde el {d}", empty_stats: "Nada todavía.", empty_stats_sub: "La pared escribe una línea cada vez que cambia el cuadro.", nothing_yet: "nada todavía",
      shown: "cuadros mostrados", works: "obras distintas", on_wall: "en la pared", skipped: "saltados", with_music: "con música",
      museums: "Museos", time_on_wall: "tiempo en la pared", centuries: "Siglos", century: "siglo {n}", painters: "Pintores", most_on_wall: "más tiempo en la pared", most_shown: "Más mostrados", sec_skipped: "Saltados", skipped_sub: "los que pasaste de largo", music: "Música", music_sub: "los artistas detrás de la pared", songs: "Canciones", pairings: "Parejas", pairings_sub: "músico → pintor emparejado más veces", of: "{a} de {b}", by_museum: "por museo", songs_hearts: "Canciones detrás de los corazones", hours: "Horas", hours_sub: "cuándo está encendida la pared", h: "h", min: "min",
    },
    it: { name: "Italiano",
      mood: "in accordo con la copertina dell’album",
      tip_theme: "Colore della parete", tip_swap: "Un altro quadro", tip_keep: "Tieni questo", tip_kept: "Quadri tenuti", tip_next: "Prossimo brano", tip_prefs: "Lingua, luogo, unità",
      st_loading: "caricamento del quadro", st_museum: "il museo non risponde, ne proviamo un altro", st_choosing: "scelta di un altro quadro", st_reading: "lettura della copertina", st_next: "prossimo brano", st_player: "il lettore non risponde",
      playing: "in riproduzione", paused: "in pausa", paused_rot: "in pausa · la parete ruota",
      sunset_in: "tramonto tra {n} min", blue_hour: "ora blu", set_at: "sole tramontato alle {t}", first_light_in: "prima luce tra {n} min", blue_morning: "ora blu del mattino", rise_at: "sorto alle {t}",
      clear: "Cielo sereno", mostly_clear: "Quasi sereno", partly: "Parzialmente nuvoloso", overcast: "Coperto", fog: "Nebbia", rime: "Nebbia gelata", drizzle_l: "Pioggerella leggera", drizzle: "Pioggerella", drizzle_d: "Pioggerella fitta", fdrizzle: "Pioggerella gelata", rain_l: "Pioggia leggera", rain: "Pioggia", rain_h: "Pioggia forte", frain: "Pioggia gelata", snow_l: "Neve leggera", snow: "Neve", snow_h: "Neve forte", showers: "Rovesci", showers_h: "Rovesci forti", snow_showers: "Rovesci di neve", storm: "Temporale",
      language: "Lingua", place: "Luogo", search_city: "cerca una città", my_position: "usa la mia posizione", locating: "localizzazione…", not_found: "nessun luogo trovato", no_position: "posizione non disponibile", units: "Unità", reset: "torna a config.json", update: "nuova versione {v} disponibile",
      kept: "Tenuti", wall: "parete", stats: "statistiche", museum: "museo", order: "ordine", newest: "recenti", oldest: "vecchi", artist: "artista", all: "tutti", empty_kept: "Niente di tenuto per ora. Premi L sulla parete.", open: "apri", remove: "rimuovi", song_tip: "suonava quando l’hai tenuto",
      since: "dal {d}", empty_stats: "Niente per ora.", empty_stats_sub: "La parete scrive una riga a ogni cambio di quadro.", nothing_yet: "niente per ora",
      shown: "quadri mostrati", works: "opere diverse", on_wall: "sulla parete", skipped: "saltati", with_music: "con musica",
      museums: "Musei", time_on_wall: "tempo sulla parete", centuries: "Secoli", century: "{n}° secolo", painters: "Pittori", most_on_wall: "più a lungo sulla parete", most_shown: "Più mostrati", sec_skipped: "Saltati", skipped_sub: "quelli che hai saltato", music: "Musica", music_sub: "gli artisti dietro la parete", songs: "Brani", pairings: "Coppie", pairings_sub: "musicista → pittore abbinato più spesso", of: "{a} su {b}", by_museum: "per museo", songs_hearts: "Brani dietro i cuori", hours: "Ore", hours_sub: "quando la parete è accesa", h: "h", min: "min",
    },
    pt: { name: "Português",
      mood: "a combinar com a capa do álbum",
      tip_theme: "Cor da parede", tip_swap: "Outro quadro", tip_keep: "Guardar este", tip_kept: "Quadros guardados", tip_next: "Próxima música", tip_prefs: "Idioma, lugar, unidades",
      st_loading: "a carregar o quadro", st_museum: "o museu não responde, a tentar outro", st_choosing: "a escolher outro quadro", st_reading: "a ler a capa do álbum", st_next: "próxima música", st_player: "o leitor não responde",
      playing: "a tocar", paused: "em pausa", paused_rot: "em pausa · a parede roda",
      sunset_in: "pôr do sol em {n} min", blue_hour: "hora azul", set_at: "sol posto às {t}", first_light_in: "primeira luz em {n} min", blue_morning: "hora azul da manhã", rise_at: "nascido às {t}",
      clear: "Céu limpo", mostly_clear: "Quase limpo", partly: "Parcialmente nublado", overcast: "Encoberto", fog: "Nevoeiro", rime: "Nevoeiro gelado", drizzle_l: "Chuvisco fraco", drizzle: "Chuvisco", drizzle_d: "Chuvisco denso", fdrizzle: "Chuvisco gelado", rain_l: "Chuva fraca", rain: "Chuva", rain_h: "Chuva forte", frain: "Chuva gelada", snow_l: "Neve fraca", snow: "Neve", snow_h: "Neve forte", showers: "Aguaceiros", showers_h: "Aguaceiros fortes", snow_showers: "Aguaceiros de neve", storm: "Trovoada",
      language: "Idioma", place: "Lugar", search_city: "procurar uma cidade", my_position: "usar a minha posição", locating: "a localizar…", not_found: "nenhum lugar encontrado", no_position: "posição indisponível", units: "Unidades", reset: "voltar a config.json", update: "nova versão {v} disponível",
      kept: "Guardados", wall: "parede", stats: "estatísticas", museum: "museu", order: "ordem", newest: "recentes", oldest: "antigos", artist: "artista", all: "todos", empty_kept: "Nada guardado ainda. Prima L na parede.", open: "abrir", remove: "remover", song_tip: "tocava quando guardou este",
      since: "desde {d}", empty_stats: "Nada ainda.", empty_stats_sub: "A parede escreve uma linha a cada mudança de quadro.", nothing_yet: "nada ainda",
      shown: "quadros mostrados", works: "obras diferentes", on_wall: "na parede", skipped: "saltados", with_music: "com música",
      museums: "Museus", time_on_wall: "tempo na parede", centuries: "Séculos", century: "século {n}", painters: "Pintores", most_on_wall: "mais tempo na parede", most_shown: "Mais mostrados", sec_skipped: "Saltados", skipped_sub: "os que passou à frente", music: "Música", music_sub: "os artistas por trás da parede", songs: "Músicas", pairings: "Pares", pairings_sub: "músico → pintor mais vezes emparelhado", of: "{a} de {b}", by_museum: "por museu", songs_hearts: "Músicas por trás dos corações", hours: "Horas", hours_sub: "quando a parede está ligada", h: "h", min: "min",
    },
    fi: { name: "Suomi",
      mood: "sovitettu albumin kanteen",
      tip_theme: "Seinän väri", tip_swap: "Toinen maalaus", tip_keep: "Pidä tämä", tip_kept: "Pidetyt maalaukset", tip_next: "Seuraava kappale", tip_prefs: "Kieli, paikka, yksiköt",
      st_loading: "ladataan maalausta", st_museum: "museo ei vastaa, kokeillaan toista", st_choosing: "valitaan toista maalausta", st_reading: "luetaan albumin kantta", st_next: "seuraava kappale", st_player: "soitin ei vastaa",
      playing: "soi", paused: "tauolla", paused_rot: "tauolla · seinä vaihtuu",
      sunset_in: "auringonlasku {n} min kuluttua", blue_hour: "sininen hetki", set_at: "aurinko laski klo {t}", first_light_in: "ensimmäinen valo {n} min kuluttua", blue_morning: "aamun sininen hetki", rise_at: "nousi klo {t}",
      clear: "Selkeää", mostly_clear: "Enimmäkseen selkeää", partly: "Puolipilvistä", overcast: "Pilvistä", fog: "Sumua", rime: "Jäätävää sumua", drizzle_l: "Heikkoa tihkua", drizzle: "Tihkua", drizzle_d: "Sankkaa tihkua", fdrizzle: "Jäätävää tihkua", rain_l: "Heikkoa sadetta", rain: "Sadetta", rain_h: "Rankkasadetta", frain: "Jäätävää sadetta", snow_l: "Heikkoa lumisadetta", snow: "Lumisadetta", snow_h: "Runsasta lumisadetta", showers: "Sadekuuroja", showers_h: "Voimakkaita kuuroja", snow_showers: "Lumikuuroja", storm: "Ukkosta",
      language: "Kieli", place: "Paikka", search_city: "hae kaupunkia", my_position: "käytä sijaintiani", locating: "paikannetaan…", not_found: "paikkaa ei löytynyt", no_position: "sijainti ei saatavilla", units: "Yksiköt", reset: "palauta config.json", update: "uusi versio {v} saatavilla",
      kept: "Pidetyt", wall: "seinä", stats: "tilastot", museum: "museo", order: "järjestys", newest: "uusimmat", oldest: "vanhimmat", artist: "taiteilija", all: "kaikki", empty_kept: "Ei vielä pidettyjä. Paina L seinällä.", open: "avaa", remove: "poista", song_tip: "soi, kun pidit tämän",
      since: "alkaen {d}", empty_stats: "Ei vielä mitään.", empty_stats_sub: "Seinä kirjoittaa rivin joka kerta, kun maalaus vaihtuu.", nothing_yet: "ei vielä mitään",
      shown: "maalausta näytetty", works: "eri teosta", on_wall: "seinällä", skipped: "ohitettu", with_music: "musiikin kanssa",
      museums: "Museot", time_on_wall: "aika seinällä", centuries: "Vuosisadat", century: "{c}00-luku", painters: "Taidemaalarit", most_on_wall: "eniten seinällä", most_shown: "Eniten näytetyt", sec_skipped: "Ohitetut", skipped_sub: "ne, jotka ohitit", music: "Musiikki", music_sub: "artistit seinän takana", songs: "Kappaleet", pairings: "Parit", pairings_sub: "artisti → useimmin yhdistetty maalari", of: "{a} / {b}", by_museum: "museon mukaan", songs_hearts: "Kappaleet sydänten takana", hours: "Tunnit", hours_sub: "milloin seinä on päällä", h: "t", min: "min",
    },
    sv: { name: "Svenska",
      mood: "matchad mot albumomslaget",
      tip_theme: "Väggfärg", tip_swap: "En annan målning", tip_keep: "Behåll den här", tip_kept: "Behållna målningar", tip_next: "Nästa låt", tip_prefs: "Språk, plats, enheter",
      st_loading: "laddar målningen", st_museum: "museet svarar inte, provar ett annat", st_choosing: "väljer en annan målning", st_reading: "läser albumomslaget", st_next: "nästa låt", st_player: "spelaren svarar inte",
      playing: "spelar", paused: "pausad", paused_rot: "pausad · väggen byter",
      sunset_in: "solnedgång om {n} min", blue_hour: "blå timmen", set_at: "solen gick ner {t}", first_light_in: "första ljuset om {n} min", blue_morning: "morgonens blå timme", rise_at: "gick upp {t}",
      clear: "Klart", mostly_clear: "Mestadels klart", partly: "Halvklart", overcast: "Mulet", fog: "Dimma", rime: "Underkyld dimma", drizzle_l: "Lätt duggregn", drizzle: "Duggregn", drizzle_d: "Tätt duggregn", fdrizzle: "Underkylt duggregn", rain_l: "Lätt regn", rain: "Regn", rain_h: "Kraftigt regn", frain: "Underkylt regn", snow_l: "Lätt snöfall", snow: "Snö", snow_h: "Kraftigt snöfall", showers: "Skurar", showers_h: "Kraftiga skurar", snow_showers: "Snöbyar", storm: "Åska",
      language: "Språk", place: "Plats", search_city: "sök en stad", my_position: "använd min position", locating: "lokaliserar…", not_found: "ingen plats hittades", no_position: "position inte tillgänglig", units: "Enheter", reset: "tillbaka till config.json", update: "ny version {v} tillgänglig",
      kept: "Behållna", wall: "vägg", stats: "statistik", museum: "museum", order: "ordning", newest: "nyaste", oldest: "äldsta", artist: "konstnär", all: "alla", empty_kept: "Inget behållet än. Tryck L på väggen.", open: "öppna", remove: "ta bort", song_tip: "spelades när du behöll den här",
      since: "sedan {d}", empty_stats: "Inget än.", empty_stats_sub: "Väggen skriver en rad varje gång målningen byts.", nothing_yet: "inget än",
      shown: "målningar visade", works: "olika verk", on_wall: "på väggen", skipped: "överhoppade", with_music: "med musik",
      museums: "Museer", time_on_wall: "tid på väggen", centuries: "Århundraden", century: "{c}00-talet", painters: "Målare", most_on_wall: "mest på väggen", most_shown: "Mest visade", sec_skipped: "Överhoppade", skipped_sub: "de du gick vidare från", music: "Musik", music_sub: "artisterna bakom väggen", songs: "Låtar", pairings: "Par", pairings_sub: "artist → oftast matchad målare", of: "{a} av {b}", by_museum: "per museum", songs_hearts: "Låtarna bakom hjärtana", hours: "Timmar", hours_sub: "när väggen är på", h: "h", min: "min",
    },
    da: { name: "Dansk",
      mood: "matchet til albumcoveret",
      tip_theme: "Vægfarve", tip_swap: "Et andet maleri", tip_keep: "Behold dette", tip_kept: "Beholdte malerier", tip_next: "Næste sang", tip_prefs: "Sprog, sted, enheder",
      st_loading: "henter maleriet", st_museum: "museet svarer ikke, prøver et andet", st_choosing: "vælger et andet maleri", st_reading: "læser albumcoveret", st_next: "næste sang", st_player: "afspilleren svarer ikke",
      playing: "spiller", paused: "på pause", paused_rot: "på pause · væggen skifter",
      sunset_in: "solnedgang om {n} min", blue_hour: "den blå time", set_at: "solen gik ned kl. {t}", first_light_in: "første lys om {n} min", blue_morning: "morgenens blå time", rise_at: "stod op kl. {t}",
      clear: "Klar himmel", mostly_clear: "Mest klart", partly: "Delvist skyet", overcast: "Overskyet", fog: "Tåge", rime: "Rimtåge", drizzle_l: "Let finregn", drizzle: "Finregn", drizzle_d: "Tæt finregn", fdrizzle: "Underafkølet finregn", rain_l: "Let regn", rain: "Regn", rain_h: "Kraftig regn", frain: "Isslag", snow_l: "Let sne", snow: "Sne", snow_h: "Kraftig sne", showers: "Byger", showers_h: "Kraftige byger", snow_showers: "Snebyger", storm: "Tordenvejr",
      language: "Sprog", place: "Sted", search_city: "søg en by", my_position: "brug min position", locating: "finder position…", not_found: "ingen sted fundet", no_position: "position ikke tilgængelig", units: "Enheder", reset: "tilbage til config.json", update: "ny version {v} tilgængelig",
      kept: "Beholdt", wall: "væg", stats: "statistik", museum: "museum", order: "rækkefølge", newest: "nyeste", oldest: "ældste", artist: "kunstner", all: "alle", empty_kept: "Intet beholdt endnu. Tryk L på væggen.", open: "åbn", remove: "fjern", song_tip: "spillede, da du beholdt dette",
      since: "siden {d}", empty_stats: "Intet endnu.", empty_stats_sub: "Væggen skriver en linje, hver gang maleriet skifter.", nothing_yet: "intet endnu",
      shown: "malerier vist", works: "forskellige værker", on_wall: "på væggen", skipped: "sprunget over", with_music: "med musik",
      museums: "Museer", time_on_wall: "tid på væggen", centuries: "Århundreder", century: "{c}00-tallet", painters: "Malere", most_on_wall: "mest på væggen", most_shown: "Mest viste", sec_skipped: "Sprunget over", skipped_sub: "dem du gik videre fra", music: "Musik", music_sub: "kunstnerne bag væggen", songs: "Sange", pairings: "Par", pairings_sub: "musiker → oftest matchet maler", of: "{a} af {b}", by_museum: "pr. museum", songs_hearts: "Sangene bag hjerterne", hours: "Timer", hours_sub: "når væggen er tændt", h: "t", min: "min",
    },
    pl: { name: "Polski",
      mood: "dopasowane do okładki albumu",
      tip_theme: "Kolor ściany", tip_swap: "Inny obraz", tip_keep: "Zachowaj ten", tip_kept: "Zachowane obrazy", tip_next: "Następny utwór", tip_prefs: "Język, miejsce, jednostki",
      st_loading: "ładowanie obrazu", st_museum: "muzeum nie odpowiada, próbujemy innego", st_choosing: "wybieranie innego obrazu", st_reading: "odczyt okładki albumu", st_next: "następny utwór", st_player: "odtwarzacz nie odpowiada",
      playing: "gra", paused: "pauza", paused_rot: "pauza · ściana się zmienia",
      sunset_in: "zachód słońca za {n} min", blue_hour: "niebieska godzina", set_at: "słońce zaszło o {t}", first_light_in: "pierwsze światło za {n} min", blue_morning: "poranna niebieska godzina", rise_at: "wzeszło o {t}",
      clear: "Bezchmurnie", mostly_clear: "Prawie bezchmurnie", partly: "Częściowe zachmurzenie", overcast: "Pochmurno", fog: "Mgła", rime: "Mgła marznąca", drizzle_l: "Lekka mżawka", drizzle: "Mżawka", drizzle_d: "Gęsta mżawka", fdrizzle: "Mżawka marznąca", rain_l: "Lekki deszcz", rain: "Deszcz", rain_h: "Ulewny deszcz", frain: "Deszcz marznący", snow_l: "Lekki śnieg", snow: "Śnieg", snow_h: "Intensywny śnieg", showers: "Przelotne opady", showers_h: "Silne przelotne opady", snow_showers: "Przelotny śnieg", storm: "Burza",
      language: "Język", place: "Miejsce", search_city: "szukaj miasta", my_position: "użyj mojej pozycji", locating: "ustalanie pozycji…", not_found: "nie znaleziono miejsca", no_position: "pozycja niedostępna", units: "Jednostki", reset: "wróć do config.json", update: "nowa wersja {v} dostępna",
      kept: "Zachowane", wall: "ściana", stats: "statystyki", museum: "muzeum", order: "kolejność", newest: "najnowsze", oldest: "najstarsze", artist: "artysta", all: "wszystkie", empty_kept: "Nic jeszcze nie zachowano. Naciśnij L na ścianie.", open: "otwórz", remove: "usuń", song_tip: "grało, gdy to zachowano",
      since: "od {d}", empty_stats: "Jeszcze nic.", empty_stats_sub: "Ściana zapisuje wiersz przy każdej zmianie obrazu.", nothing_yet: "jeszcze nic",
      shown: "obrazów pokazanych", works: "różnych dzieł", on_wall: "na ścianie", skipped: "pominięte", with_music: "z muzyką",
      museums: "Muzea", time_on_wall: "czas na ścianie", centuries: "Wieki", century: "{n}. wiek", painters: "Malarze", most_on_wall: "najdłużej na ścianie", most_shown: "Najczęściej pokazywane", sec_skipped: "Pominięte", skipped_sub: "te, które pominięto", music: "Muzyka", music_sub: "artyści za ścianą", songs: "Utwory", pairings: "Pary", pairings_sub: "muzyk → najczęściej dopasowany malarz", of: "{a} z {b}", by_museum: "według muzeum", songs_hearts: "Utwory za serduszkami", hours: "Godziny", hours_sub: "kiedy ściana jest włączona", h: "godz", min: "min",
    },
    ru: { name: "Русский",
      mood: "подобрано к обложке альбома",
      tip_theme: "Цвет стены", tip_swap: "Другая картина", tip_keep: "Оставить эту", tip_kept: "Оставленные картины", tip_next: "Следующая песня", tip_prefs: "Язык, место, единицы",
      st_loading: "загрузка картины", st_museum: "музей не отвечает, пробуем другой", st_choosing: "выбор другой картины", st_reading: "чтение обложки альбома", st_next: "следующая песня", st_player: "плеер не отвечает",
      playing: "играет", paused: "пауза", paused_rot: "пауза · стена меняется",
      sunset_in: "закат через {n} мин", blue_hour: "синий час", set_at: "солнце зашло в {t}", first_light_in: "первый свет через {n} мин", blue_morning: "утренний синий час", rise_at: "взошло в {t}",
      clear: "Ясно", mostly_clear: "Почти ясно", partly: "Переменная облачность", overcast: "Пасмурно", fog: "Туман", rime: "Изморозь", drizzle_l: "Лёгкая морось", drizzle: "Морось", drizzle_d: "Густая морось", fdrizzle: "Ледяная морось", rain_l: "Небольшой дождь", rain: "Дождь", rain_h: "Сильный дождь", frain: "Ледяной дождь", snow_l: "Небольшой снег", snow: "Снег", snow_h: "Сильный снег", showers: "Ливни", showers_h: "Сильные ливни", snow_showers: "Снежные заряды", storm: "Гроза",
      language: "Язык", place: "Место", search_city: "найти город", my_position: "использовать моё положение", locating: "определение…", not_found: "место не найдено", no_position: "положение недоступно", units: "Единицы", reset: "вернуть config.json", update: "доступна новая версия {v}",
      kept: "Оставленные", wall: "стена", stats: "статистика", museum: "музей", order: "порядок", newest: "новые", oldest: "старые", artist: "художник", all: "все", empty_kept: "Пока ничего не оставлено. Нажмите L на стене.", open: "открыть", remove: "убрать", song_tip: "играло, когда вы оставили это",
      since: "с {d}", empty_stats: "Пока ничего.", empty_stats_sub: "Стена пишет строку при каждой смене картины.", nothing_yet: "пока ничего",
      shown: "картин показано", works: "разных работ", on_wall: "на стене", skipped: "пропущено", with_music: "с музыкой",
      museums: "Музеи", time_on_wall: "время на стене", centuries: "Века", century: "{n} век", painters: "Художники", most_on_wall: "дольше всех на стене", most_shown: "Чаще всего показаны", sec_skipped: "Пропущенные", skipped_sub: "те, что вы пролистнули", music: "Музыка", music_sub: "артисты за стеной", songs: "Песни", pairings: "Пары", pairings_sub: "музыкант → чаще всего подобранный художник", of: "{a} из {b}", by_museum: "по музеям", songs_hearts: "Песни за сердечками", hours: "Часы", hours_sub: "когда стена включена", h: "ч", min: "мин",
    },
    ja: { name: "日本語",
      mood: "アルバムジャケットに合わせて",
      tip_theme: "壁の色", tip_swap: "別の絵", tip_keep: "この絵を残す", tip_kept: "残した絵", tip_next: "次の曲", tip_prefs: "言語・場所・単位",
      st_loading: "絵を読み込み中", st_museum: "美術館が応答しません。別の絵を試します", st_choosing: "別の絵を選んでいます", st_reading: "ジャケットを読み取り中", st_next: "次の曲", st_player: "プレーヤーが応答しません",
      playing: "再生中", paused: "一時停止", paused_rot: "一時停止 · 壁は回ります",
      sunset_in: "日没まで{n}分", blue_hour: "ブルーアワー", set_at: "{t}に日没", first_light_in: "日の出まで{n}分", blue_morning: "朝のブルーアワー", rise_at: "{t}に日の出",
      clear: "快晴", mostly_clear: "晴れ", partly: "薄曇り", overcast: "曇り", fog: "霧", rime: "着氷性の霧", drizzle_l: "弱い霧雨", drizzle: "霧雨", drizzle_d: "強い霧雨", fdrizzle: "着氷性の霧雨", rain_l: "小雨", rain: "雨", rain_h: "大雨", frain: "着氷性の雨", snow_l: "小雪", snow: "雪", snow_h: "大雪", showers: "にわか雨", showers_h: "強いにわか雨", snow_showers: "にわか雪", storm: "雷雨",
      language: "言語", place: "場所", search_city: "都市を検索", my_position: "現在地を使う", locating: "位置を取得中…", not_found: "場所が見つかりません", no_position: "位置を取得できません", units: "単位", reset: "config.json に戻す", update: "新しいバージョン {v} があります",
      kept: "残した絵", wall: "壁", stats: "統計", museum: "美術館", order: "並び順", newest: "新しい順", oldest: "古い順", artist: "作者", all: "すべて", empty_kept: "まだ何も残していません。壁で L を押してください。", open: "開く", remove: "削除", song_tip: "残したときに流れていた曲",
      since: "{d}から", empty_stats: "まだありません。", empty_stats_sub: "絵が変わるごとに壁が1行書きます。", nothing_yet: "まだありません",
      shown: "表示した絵", works: "異なる作品", on_wall: "壁にいた時間", skipped: "スキップ", with_music: "音楽あり",
      museums: "美術館", time_on_wall: "壁にいた時間", centuries: "世紀", century: "{n}世紀", painters: "画家", most_on_wall: "最も長く壁に", most_shown: "最も多く表示", sec_skipped: "スキップした絵", skipped_sub: "飛ばした絵", music: "音楽", music_sub: "壁の裏のアーティスト", songs: "曲", pairings: "組み合わせ", pairings_sub: "アーティスト → 最も多く合わせた画家", of: "{b}中{a}", by_museum: "美術館別", songs_hearts: "ハートの裏の曲", hours: "時間帯", hours_sub: "壁がついている時間", h: "時間", min: "分",
    },
  };

  // Open-Meteo WMO weather code -> label key
  const WMO = { 0: "clear", 1: "mostly_clear", 2: "partly", 3: "overcast", 45: "fog", 48: "rime", 51: "drizzle_l", 53: "drizzle", 55: "drizzle_d", 56: "fdrizzle", 57: "fdrizzle",
    61: "rain_l", 63: "rain", 65: "rain_h", 66: "frain", 67: "frain", 71: "snow_l", 73: "snow", 75: "snow_h", 77: "snow_l", 80: "showers", 81: "showers", 82: "showers_h", 85: "snow_showers", 86: "snow_showers", 95: "storm", 96: "storm", 99: "storm" };

  const params = new URLSearchParams(location.search);
  const LS = { lang: "wall.lang", city: "wall.city", units: "wall.units" };
  let CFG = { locale: "", language: "", city: { name: "Paris", lat: 48.8566, lon: 2.3522, timezone: "Europe/Paris" }, units: "celsius" };
  let lang = "en";

  const norm = (code) => { const c = String(code || "").toLowerCase().slice(0, 2); return LANGS[c] ? c : null; };
  function pickLang() {
    const fromUrl = norm(params.get("lang"));
    if (fromUrl) { localStorage.setItem(LS.lang, fromUrl); return fromUrl; }
    return norm(localStorage.getItem(LS.lang)) || norm(CFG.language) || norm(CFG.locale) || norm(navigator.language) || "en";
  }
  function t(key, vars) {
    let s = (LANGS[lang] && LANGS[lang][key]) ?? LANGS.en[key] ?? key;
    if (vars) for (const k in vars) s = s.replaceAll(`{${k}}`, vars[k]);
    return s;
  }
  // static text: <el data-i18n="key">, titles: <el data-i18n-title="key">, placeholders: <el data-i18n-ph="key">
  function apply(root = document) {
    document.documentElement.lang = lang;
    root.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
    root.querySelectorAll("[data-i18n-title]").forEach(el => { el.title = t(el.dataset.i18nTitle); });
    root.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
    const ti = document.querySelector("title[data-i18n-doc]"); if (ti) ti.textContent = t(ti.dataset.i18nDoc);
    document.dispatchEvent(new CustomEvent("hb:lang", { detail: { lang } }));
  }
  function setLang(code) { const c = norm(code); if (!c) return; lang = c; localStorage.setItem(LS.lang, c); apply(); }
  // the regional date format follows config.json when its language matches the one on screen
  const dateLocale = () => (String(CFG.locale || "").toLowerCase().startsWith(lang) ? CFG.locale : lang);
  const ordinal = (n) => { const r = n % 100; if (r >= 11 && r <= 13) return `${n}th`; return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"); };
  const century = (n) => lang === "en" ? `${ordinal(n)} century` : t("century", { n, c: n - 1 });
  const wmo = (code) => t(WMO[code] || "partly");

  // place and units: browser choice over config.json
  function city() { try { const c = JSON.parse(localStorage.getItem(LS.city) || "null"); if (c && c.lat != null && c.lon != null) return c; } catch (e) {} return CFG.city; }
  function setCity(c) { if (c) localStorage.setItem(LS.city, JSON.stringify({ name: c.name, lat: +c.lat, lon: +c.lon, timezone: c.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone })); else localStorage.removeItem(LS.city); document.dispatchEvent(new CustomEvent("hb:place")); }
  const units = () => localStorage.getItem(LS.units) || CFG.units || "celsius";
  function setUnits(u) { localStorage.setItem(LS.units, u === "fahrenheit" ? "fahrenheit" : "celsius"); document.dispatchEvent(new CustomEvent("hb:place")); }
  function reset() { [LS.lang, LS.city, LS.units].forEach(k => localStorage.removeItem(k)); lang = pickLang(); apply(); document.dispatchEvent(new CustomEvent("hb:place")); }
  const overridden = () => !!(localStorage.getItem(LS.lang) || localStorage.getItem(LS.city) || localStorage.getItem(LS.units));

  // Open-Meteo geocoding, no key. Names come back in the language on screen when it has them.
  async function searchCity(q) {
    const u = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=6&language=${lang}&format=json`;
    const j = await (await fetch(u)).json();
    return (j.results || []).map(r => ({ name: r.name, detail: [r.admin1, r.country].filter(Boolean).join(", "), lat: r.latitude, lon: r.longitude, timezone: r.timezone }));
  }
  // the browser's position; the name comes from a free reverse lookup, else the coordinates
  function locate() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) return reject(new Error("no geolocation"));
      navigator.geolocation.getCurrentPosition(async (pos) => {
        const lat = +pos.coords.latitude.toFixed(4), lon = +pos.coords.longitude.toFixed(4);
        let name = `${lat}, ${lon}`;
        try {
          const j = await (await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=${lang}`)).json();
          name = j.city || j.locality || j.principalSubdivision || name;
        } catch (e) {}
        resolve({ name, lat, lon, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone });
      }, reject, { timeout: 10000, maximumAge: 600000 });
    });
  }

  // init: merge /api/config (the real server or the demo shim), then pick the language and translate the page
  let ready;
  function init(cfg) {
    if (ready) return ready;
    ready = (async () => {
      if (cfg) CFG = { ...CFG, ...cfg };
      else { try { CFG = { ...CFG, ...(await (await fetch("/api/config", { cache: "no-store" })).json()) }; } catch (e) {} }
      lang = pickLang(); apply();
      return CFG;
    })();
    return ready;
  }
  lang = pickLang(); // a first pass before the config arrives, so the page never flashes the wrong language

  window.HB = { LANGS, t, apply, init, setLang, get lang() { return lang; }, dateLocale, century, wmo, city, setCity, units, setUnits, reset, overridden, searchCity, locate, get cfg() { return CFG; } };
})();
