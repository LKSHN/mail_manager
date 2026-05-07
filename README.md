# Gmail Desktop App — Python

Application bureau pour gérer sa boîte Gmail via l'API Google.

## Installation

### 1. Prérequis
- Python 3.8+
- Tkinter (inclus dans Python sur Windows/macOS ; sur Linux : `sudo apt install python3-tk`)

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Placer ton fichier credentials.json
- Va sur https://console.cloud.google.com
- Ouvre ton projet → API et services → Identifiants
- Télécharge le fichier OAuth 2.0 (type "Application de bureau")
- Renomme-le `credentials.json` et place-le dans ce dossier

### 4. Lancer l'application
```bash
python gmail_app.py
```

La première fois, un navigateur s'ouvre pour te demander d'autoriser l'accès.
Un fichier `token.json` est ensuite créé automatiquement (ne pas le partager).

---

## Fonctionnalités

### 📬 Lecture des mails
- Affichage des 50 derniers messages
- Filtre par boîte (INBOX, SENT, STARRED, SPAM, TRASH, libellés perso)
- Lecture du corps du message au clic
- Marquage automatique comme lu

### 🔍 Recherche
- Supporte tous les opérateurs Gmail : `from:`, `subject:`, `has:attachment`, etc.

### ✏️ Envoi
- Composer un nouveau message
- Répondre à un message sélectionné

### 🏷️ Libellés
- Voir tous ses libellés
- Créer un nouveau libellé
- Supprimer un libellé
- Appliquer un libellé à un ou plusieurs messages (clic droit)

### 🧹 Nettoyage en masse
- Archiver/supprimer tous les mails d'un expéditeur
- Archiver/supprimer par mot-clé dans le sujet
- Actions rapides : vider Promotions, vider Spam, archiver tous les lus

### ⚡ Actions rapides (clic droit ou boutons)
- Archiver
- Mettre à la corbeille
- Marquer comme lu
- Marquer d'une étoile
