import re
from django.db import models

class Plural(models.Model):
    """Remember the plural of product and unit names.
    Django supports plurals for words occurring verbatim in templates,
    but not for words coming from the DB."""
    singular = models.CharField(max_length=64, unique=True)
    plural = models.CharField(max_length=64, null=True, blank=True, default=None)

    def __unicode__(self):
        return "%s/%s" % (self.singular, self.plural)


# Cache for plurals, to avoid many DB lookups when a pluralized word appears many times in a page.
_plural_cache = {}
_unit_re = re.compile('^[0-9]+[a-z]+$')

def plural(noun, n=None):
    """Tries to retrieve of guess the plural of a singular French word.
    It would be great to hook this up to a (possibly online) dictionary.

    :param noun: the French noun to try and pluralize
    :param n: number of stuff (optional): don't pluralize if |n| < 2.
    :return: pluralized noun."""

    if n is not None and -2 < n < 2:
        return noun  # No need to pluralize

    try:
        return _plural_cache[noun]  # Found in cache
    except KeyError:
        pass

    try:
        r = Plural.objects.get(singular=noun).plural
        if r is not None:
            _plural_cache[noun] = r
            return r
    except Plural.DoesNotExist:
        # Put the singular alone in DB, so that we know it needs to be filled
        Plural.objects.create(singular=noun, plural=None)

    # Not found in DB, or found to be None: try to guess it
    if " " in noun:
        r = noun  # Don't try to guess whole expressions
    if noun[-1] == 's' or noun[-1] == 'x':
        r = noun  # Probably invariant
    elif noun[-2:] == 'al':
        r = noun[:-2] + 'aux'
    elif noun[-3:] == 'eau':
        r = noun + 'x'
    elif _unit_re.match(noun):
        r = noun
    else:
        r = noun + 's'  # bet on a regular plural

    _plural_cache[noun] = r
    return r


def articulate(noun, n=1):
    """Prepend an appropriate French article to a word.
    Caveat: doesn't handle 'y' nor 'h' correctly.

    :param noun: the noun in need of an article
    :param n: quantity of the noun, to determine whether it needs to be pluralized
    :return: the noun with an indefinite article, possibly in the plural form."""

    if 'aeiou'.count(noun[0].lower()):
        return "d'" + plural(noun, n)
    else:
        return "de " + plural(noun, n)

