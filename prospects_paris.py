"""
Script de prospection de commerces locaux parisiens sans site web
via l'API Google Places.

Utilisation :
    1. Remplacez YOUR_API_KEY par votre clé API Google Places.
    2. Lancez : python prospects_paris.py
    3. Récupérez le fichier "prospects_paris.csv" généré.
"""

# ─────────────────────────────────────────────
# 0. Installation automatique des dépendances
# ─────────────────────────────────────────────
import subprocess
import sys

def installer_dependances():
    """Installe requests et pandas si absents."""
    paquets = ["requests", "pandas"]
    for paquet in paquets:
        try:
            __import__(paquet)
        except ImportError:
            print(f"Installation de {paquet}…")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", paquet],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

installer_dependances()

# ─────────────────────────────────────────────
# 1. Imports principaux
# ─────────────────────────────────────────────
import time
import csv
import requests
import pandas as pd

# ─────────────────────────────────────────────
# 2. Configuration — remplacez la clé API ici
# ─────────────────────────────────────────────
GOOGLE_API_KEY = "YOUR_API_KEY"

# Fichier de sortie
FICHIER_CSV = "prospects_paris.csv"

# Pause entre chaque appel API (secondes) — évite d'être bloqué par Google
DELAI_API = 0.3

# ─────────────────────────────────────────────
# 3. Définition des zones de recherche
#    Format : (type_google_places, label_lisible, liste_arrondissements)
# ─────────────────────────────────────────────
ZONES_RECHERCHE = [
    # Restaurants dans les arrondissements populaires
    ("restaurant",          "Restaurant",       ["Paris 10", "Paris 11", "Paris 13", "Paris 18", "Paris 19", "Paris 20"]),
    # Coiffeurs et barbiers
    ("hair_care",           "Coiffeur/Barbier",  ["Paris 9",  "Paris 15", "Paris 18"]),
    # Nail bars et instituts de beauté
    ("beauty_salon",        "Nail bar/Beauté",   ["Paris 14", "Paris 15", "Paris 17"]),
    # Plombiers
    ("plumber",             "Plombier",          ["Paris 12", "Paris 16", "Paris 17"]),
    # Électriciens
    ("electrician",         "Électricien",       ["Paris 12", "Paris 16", "Paris 17"]),
    # Pressings / blanchisseries
    ("laundry",             "Pressing",          ["Paris 12", "Paris 16", "Paris 17"]),
]

# ─────────────────────────────────────────────
# 4. Coordonnées GPS approximatives des arrondissements parisiens
#    (latitude, longitude) — utilisées comme centre de recherche
# ─────────────────────────────────────────────
COORDS_ARRONDISSEMENTS = {
    "Paris 1":  (48.8606, 2.3477),
    "Paris 2":  (48.8671, 2.3477),
    "Paris 3":  (48.8632, 2.3590),
    "Paris 4":  (48.8534, 2.3524),
    "Paris 5":  (48.8462, 2.3511),
    "Paris 6":  (48.8496, 2.3341),
    "Paris 7":  (48.8566, 2.3140),
    "Paris 8":  (48.8751, 2.3070),
    "Paris 9":  (48.8761, 2.3390),
    "Paris 10": (48.8765, 2.3631),
    "Paris 11": (48.8593, 2.3796),
    "Paris 12": (48.8404, 2.3892),
    "Paris 13": (48.8322, 2.3561),
    "Paris 14": (48.8327, 2.3274),
    "Paris 15": (48.8417, 2.2981),
    "Paris 16": (48.8632, 2.2746),
    "Paris 17": (48.8847, 2.3136),
    "Paris 18": (48.8926, 2.3444),
    "Paris 19": (48.8840, 2.3784),
    "Paris 20": (48.8640, 2.3989),
}

# Rayon de recherche en mètres (environ 600 m couvre bien un arrondissement dense)
RAYON_RECHERCHE = 600

# ─────────────────────────────────────────────
# 5. Fonctions d'appel à l'API Google Places
# ─────────────────────────────────────────────

def nearby_search(type_lieu, lat, lng, rayon=RAYON_RECHERCHE):
    """
    Appelle l'endpoint Nearby Search de Google Places.
    Renvoie une liste de place_id correspondant au type demandé
    dans le rayon autour du point (lat, lng).
    Gère la pagination automatiquement (max 3 pages = 60 résultats).
    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    place_ids = []
    params = {
        "location": f"{lat},{lng}",
        "radius": rayon,
        "type": type_lieu,
        "key": GOOGLE_API_KEY,
        "language": "fr",
    }

    while True:
        reponse = requests.get(url, params=params, timeout=10)
        reponse.raise_for_status()
        donnees = reponse.json()

        statut = donnees.get("status")
        if statut not in ("OK", "ZERO_RESULTS"):
            # Affiche l'erreur éventuelle (quota dépassé, clé invalide, etc.)
            print(f"  [Nearby Search] Statut inattendu : {statut} — {donnees.get('error_message', '')}")
            break

        for lieu in donnees.get("results", []):
            place_ids.append(lieu["place_id"])

        # Récupère la page suivante si elle existe
        next_token = donnees.get("next_page_token")
        if not next_token:
            break

        # Google exige un délai avant d'utiliser le next_page_token
        time.sleep(2)
        params = {"pagetoken": next_token, "key": GOOGLE_API_KEY}

    return place_ids


def place_details(place_id):
    """
    Appelle l'endpoint Place Details pour un place_id donné.
    Renvoie un dict avec les champs utiles à la prospection.
    """
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    champs = ",".join([
        "name",
        "formatted_address",
        "formatted_phone_number",
        "rating",
        "user_ratings_total",
        "website",
        "business_status",
        "address_components",
    ])
    params = {
        "place_id": place_id,
        "fields": champs,
        "key": GOOGLE_API_KEY,
        "language": "fr",
    }

    reponse = requests.get(url, params=params, timeout=10)
    reponse.raise_for_status()
    donnees = reponse.json()

    if donnees.get("status") != "OK":
        return None

    return donnees.get("result", {})


def extraire_arrondissement(address_components):
    """
    Extrait le code postal à partir des composantes d'adresse Google,
    puis en déduit l'arrondissement parisien (ex: 75010 → Paris 10).
    """
    for composant in address_components:
        if "postal_code" in composant.get("types", []):
            code_postal = composant.get("short_name", "")
            if code_postal.startswith("750") and len(code_postal) == 5:
                numero = int(code_postal[3:])
                if numero == 0:
                    return "Paris 1"   # 75001 → arrondissement 1
                return f"Paris {numero}"
    return "Inconnu"


# ─────────────────────────────────────────────
# 6. Critères de filtrage des prospects
# ─────────────────────────────────────────────

NOTE_MIN          = 3.0   # Note Google minimale
NOTE_MAX          = 4.4   # Note Google maximale (trop haute = déjà bien référencé)
AVIS_MIN          = 6     # Nombre minimal d'avis (strictement "plus de 5")
STATUT_REQUIS     = "OPERATIONAL"

def est_prospect_qualifie(commerce):
    """
    Retourne True si le commerce correspond à nos critères de prospection :
      - Pas de site web
      - Note comprise entre NOTE_MIN et NOTE_MAX
      - Au moins AVIS_MIN avis
      - Statut OPERATIONAL
    """
    if commerce.get("website"):
        return False
    note = commerce.get("rating")
    if note is None or not (NOTE_MIN <= note <= NOTE_MAX):
        return False
    if commerce.get("user_ratings_total", 0) < AVIS_MIN:
        return False
    if commerce.get("business_status") != STATUT_REQUIS:
        return False
    return True


# ─────────────────────────────────────────────
# 7. Programme principal
# ─────────────────────────────────────────────

def main():
    if GOOGLE_API_KEY == "YOUR_API_KEY":
        print("⚠️  Veuillez remplacer YOUR_API_KEY par votre vraie clé API Google Places.")
        sys.exit(1)

    print("=" * 60)
    print("  Prospection commerces parisiens — API Google Places")
    print("=" * 60)

    tous_les_prospects = []    # Liste finale des prospects qualifiés
    total_scannes      = 0     # Compteur total de fiches analysées
    deja_vus           = set() # Évite les doublons (même place_id)
    compteurs_type     = {}    # Répartition par type de commerce

    # Parcours de chaque zone de recherche définie
    for type_lieu, label, arrondissements in ZONES_RECHERCHE:
        print(f"\n→ Type : {label}")
        compteurs_type.setdefault(label, 0)

        for arrdt in arrondissements:
            coords = COORDS_ARRONDISSEMENTS.get(arrdt)
            if not coords:
                print(f"  Coordonnées introuvables pour {arrdt}, ignoré.")
                continue

            lat, lng = coords
            print(f"  Recherche dans {arrdt}…", end=" ", flush=True)

            # 7a. Récupère les place_id de la zone
            try:
                place_ids = nearby_search(type_lieu, lat, lng)
            except requests.RequestException as e:
                print(f"Erreur réseau : {e}")
                continue

            print(f"{len(place_ids)} établissements trouvés")

            # 7b. Pour chaque lieu, récupère les détails
            for place_id in place_ids:
                if place_id in deja_vus:
                    continue  # Déjà traité (peut apparaître dans plusieurs zones)
                deja_vus.add(place_id)
                total_scannes += 1

                time.sleep(DELAI_API)  # Respect du quota API

                try:
                    details = place_details(place_id)
                except requests.RequestException as e:
                    print(f"    Erreur détails {place_id} : {e}")
                    continue

                if details is None:
                    continue

                # Construit la fiche prospect
                adresse_composants = details.get("address_components", [])
                arrondissement_reel = extraire_arrondissement(adresse_composants)

                fiche = {
                    "nom":                details.get("name", ""),
                    "adresse":            details.get("formatted_address", ""),
                    "arrondissement":     arrondissement_reel,
                    "type_commerce":      label,
                    "note":               details.get("rating"),
                    "nombre_avis":        details.get("user_ratings_total", 0),
                    "site_web":           details.get("website", ""),        # Vide = prospect chaud
                    "telephone":          details.get("formatted_phone_number", ""),
                    "statut":             details.get("business_status", ""),
                    "place_id":           place_id,
                }

                # 7c. Applique les critères de filtrage
                if est_prospect_qualifie(fiche):
                    tous_les_prospects.append(fiche)
                    compteurs_type[label] += 1

    # ─────────────────────────────────────────────
    # 8. Export CSV
    # ─────────────────────────────────────────────
    print("\n" + "=" * 60)

    if tous_les_prospects:
        df = pd.DataFrame(tous_les_prospects)

        # Ordonne les colonnes de façon lisible
        colonnes = [
            "nom", "adresse", "arrondissement", "type_commerce",
            "note", "nombre_avis", "telephone", "site_web", "statut", "place_id",
        ]
        df = df[colonnes]

        # Trie par arrondissement puis par note décroissante
        df = df.sort_values(["arrondissement", "note"], ascending=[True, False])

        df.to_csv(FICHIER_CSV, index=False, encoding="utf-8-sig")
        # utf-8-sig = BOM UTF-8 pour compatibilité Excel français
        print(f"  Fichier exporté : {FICHIER_CSV}")
    else:
        print("  Aucun prospect qualifié trouvé.")

    # ─────────────────────────────────────────────
    # 9. Résumé terminal
    # ─────────────────────────────────────────────
    print("\n📊 RÉSUMÉ")
    print(f"  Établissements scannés      : {total_scannes}")
    print(f"  Prospects qualifiés         : {len(tous_les_prospects)}")
    print("\n  Répartition par type :")
    for label, count in compteurs_type.items():
        print(f"    {label:<25} {count} prospects")
    print("=" * 60)


if __name__ == "__main__":
    main()
