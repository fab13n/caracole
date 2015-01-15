import hmac
from hashlib import sha512

from . import models as m


KEY = "d143d4a7-1c24-42d5-a615-ae951bb1b600"


def check_legacy_password(email, password):
    try:
        stored = m.LegacyPassword.objects.get(email=email)
        if stored.migrated:
            return False, "Mot de pass incorrect (MIGRATED)"
        (digest_alg, salt, stored_digest) = stored.password.encode('ascii').split("$")
        digest = hmac.new(KEY+salt, password, sha512).hexdigest()
        if digest == stored_digest:
            return True, None
        else:
            return False, "Mot de passe incorrect (LEGACY_MISMATCH)"
    except m.LegacyPassword.DoesNotExist:
        print "Not a web2py user"
        return False, "Mot de passe incorrect (NO_LEGACY)"


def migrate_password(u, password):
    """Write the password in the main auth system, remember it has been migrated."""
    u.set_password(password)
    u.save()
    lp = m.LegacyPassword.objects.get(email=u.username)
    lp.migrated = True
    lp.save()


class LegacyBackend(object):

    def authenticate(self, username=None, password=None):
        try:
            user = m.User.objects.get(username=username)
        except m.User.DoesNotExist:
            return None
        success, msg = check_legacy_password(username, password)
        if success:
            migrate_password(user, password)
            return user
        else:
            return None

    def get_user(self, pk):
        return m.User.objects.get(pk=pk)
