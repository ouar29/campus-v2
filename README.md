- [ ] Nettoyer le code redondant après modularisation
- [ ] Eclater les vues vers des fichiers dédiés.

#### Idées
Navigation inverse : dans la table "Toutes les salles" (ou la fiche détaillée), un bouton "Localiser sur le plan" qui ferme le dialog, bascule bâtiment/étage sur la bonne sélection et centre la vue sur la salle. C'est l'exact symétrique du double-clic qu'on vient d'ajouter.


2. Qualité et intégrité des données
Finir la validation JSON schema — c'était déjà noté comme tâche ouverte : verrouiller les enums réels (roomType, access, type) extraits de model.py, pour que "Valider .cps" détecte vraiment les incohérences plutôt que de rester permissif.
Rapport d'intégrité : un dialog "Salles sans gestionnaire", "Capacité à 0 ou suspecte", "Doublons de nom de salle" — utile après un import .cps massif pour repérer les trous.
Gestionnaires orphelins : afficher/nettoyer les Gestionnaire qui ne sont assignés à aucune salle (accumulation possible après des suppressions de salles).
3. Productivité sur les tables
Tri et filtres avancés dans "Toutes les salles" : par capacité, par bâtiment, par "a un gestionnaire / n'en a pas".
Édition en masse : sélection multiple de salles pour assigner un gestionnaire à plusieurs salles d'un coup (la logique assign_gestionnaires_to_room s'y prête déjà, il manque l'UI de sélection groupée).
Import annuaire en masse : un CSV nom/email/téléphone → création groupée de Gestionnaire, pour éviter la saisie un par un.
4. Export et reporting
Export CSV/Excel de la table des salles ou des gestionnaires (facilities/RH en ont souvent besoin hors de l'appli).
Statistiques simples : capacité totale par bâtiment/étage, nombre de salles par gestionnaire — un petit dashboard, potentiellement dans le dialog "Plan du campus" existant.
5. Robustesse
Historique/undo : actuellement chaque modification sauvegarde immédiatement (app.save()), sans possibilité de revenir en arrière. Un simple undo sur la dernière action, ou un horodatage de sauvegarde automatique avec restauration, sécuriserait les manipulations en masse (import, édition groupée).