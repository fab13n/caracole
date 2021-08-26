from django.db import models


class Ville(models.Model):
    id = models.IntegerField(db_column="ville_id", primary_key=True)
    departement = models.CharField(
        db_column="ville_departement", max_length=3, blank=True, null=True
    )
    slug = models.CharField(
        db_column="ville_slug", max_length=255, blank=True, null=True
    )
    nom = models.CharField(db_column="ville_nom", max_length=45, blank=True, null=True)
    nom_simple = models.CharField(
        db_column="ville_nom_simple", max_length=45, blank=True, null=True
    )
    nom_reel = models.CharField(
        db_column="ville_nom_reel", max_length=45, blank=True, null=True
    )
    nom_soundex = models.CharField(
        db_column="ville_nom_soundex", max_length=20, blank=True, null=True
    )
    nom_metaphone = models.CharField(
        db_column="ville_nom_metaphone", max_length=22, blank=True, null=True
    )
    code_postal = models.CharField(
        db_column="ville_code_postal", max_length=255, blank=True, null=True
    )
    commune = models.CharField(
        db_column="ville_commune", max_length=3, blank=True, null=True
    )
    code_commune = models.CharField(db_column="ville_code_commune", max_length=5)
    arrondissement = models.IntegerField(
        db_column="ville_arrondissement", blank=True, null=True
    )
    canton = models.CharField(
        db_column="ville_canton", max_length=4, blank=True, null=True
    )
    amdi = models.IntegerField(db_column="ville_amdi", blank=True, null=True)
    population_2010 = models.IntegerField(
        db_column="ville_population_2010", blank=True, null=True
    )
    population_1999 = models.IntegerField(
        db_column="ville_population_1999", blank=True, null=True
    )
    population_2012 = models.IntegerField(
        db_column="ville_population_2012", blank=True, null=True
    )
    densite_2010 = models.IntegerField(
        db_column="ville_densite_2010", blank=True, null=True
    )
    surface = models.FloatField(db_column="ville_surface", blank=True, null=True)
    longitude_deg = models.FloatField(
        db_column="ville_longitude_deg", blank=True, null=True
    )
    latitude_deg = models.FloatField(
        db_column="ville_latitude_deg", blank=True, null=True
    )
    longitude_grd = models.CharField(
        db_column="ville_longitude_grd", max_length=9, blank=True, null=True
    )
    latitude_grd = models.CharField(
        db_column="ville_latitude_grd", max_length=8, blank=True, null=True
    )
    longitude_dms = models.CharField(
        db_column="ville_longitude_dms", max_length=9, blank=True, null=True
    )
    latitude_dms = models.CharField(
        db_column="ville_latitude_dms", max_length=8, blank=True, null=True
    )
    zmin = models.IntegerField(db_column="ville_zmin", blank=True, null=True)
    zmax = models.IntegerField(db_column="ville_zmax", blank=True, null=True)

    class Meta:
        db_table = "villes_france_free"
        indexes = [
            models.Index(fields=["departement"], name="departement_idx"),
            models.Index(fields=["slug"], name="slug_idx"),
            models.Index(fields=["nom"], name="nom_idx"),
            models.Index(fields=["nom_simple"], name="nom_simple_idx"),
            models.Index(fields=["nom_reel"], name="nom_reel_idx"),
            models.Index(fields=["nom_soundex"], name="nom_soundex_idx"),
            models.Index(fields=["nom_metaphone"], name="nom_metaphone_idx"),
            models.Index(fields=["code_postal"], name="code_postal_idx"),
            models.Index(fields=["commune"], name="commune_idx"),
            models.Index(fields=["code_commune"], name="code_commune_idx"),
            models.Index(fields=["arrondissement"], name="arrondissement_idx"),
            models.Index(fields=["canton"], name="canton_idx"),
            models.Index(fields=["amdi"], name="amdi_idx"),
            # models.Index(fields=['population_2010'], name='population_2010_idx'),
            # models.Index(fields=['population_1999'], name='population_1999_idx'),
            # models.Index(fields=['population_2012'], name='population_2012_idx'),
            # models.Index(fields=['densite_2010'], name='densite_2010_idx'),
            # models.Index(fields=['surface'], name='surface_idx'),
            # models.Index(fields=['longitude_deg'], name='longitude_deg_idx'),
            # models.Index(fields=['latitude_deg'], name='latitude_deg_idx'),
            # models.Index(fields=['longitude_grd'], name='longitude_grd_idx'),
            # models.Index(fields=['latitude_grd'], name='latitude_grd_idx'),
            # models.Index(fields=['longitude_dms'], name='longitude_dms_idx'),
            # models.Index(fields=['latitude_dms'], name='latitude_dms_idx'),
            # models.Index(fields=['zmin'], name='zmin_idx'),
            # models.Index(fields=['zmax'], name='zmax_idx'),
        ]

    def __str__(self):
        return self.nom_reel + " " + self.code_postal
