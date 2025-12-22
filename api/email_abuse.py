"""
Email Anti-Abuse System
Comprehensive protection against disposable emails, duplicates, and abuse
"""

import re
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# Comprehensive disposable email domain list (100+ domains)
DISPOSABLE_EMAIL_DOMAINS = {
    # Popular temporary email services
    'tempmail.com', 'throwaway.email', 'mailinator.com', 'guerrillamail.com',
    '10minutemail.com', 'temp-mail.org', 'getnada.com', 'mohmal.com',
    'yopmail.com', 'maildrop.cc', 'sharklasers.com', 'grr.la',
    'guerrillamailblock.com', 'pokemail.net', 'spam4.me', 'fakeinbox.com',
    'dispostable.com', 'mintemail.com', 'meltmail.com', 'trashmail.com',
    'throwawaymail.com', 'tempail.com', 'mytemp.email', 'emailondeck.com',
    'getairmail.com', 'mailcatch.com', 'mailmoat.com', 'mailnesia.com',
    'mailsac.com', 'mailtemp.info', 'mintemail.com', 'mytrashmail.com',
    'nada.email', 'nowmymail.com', 'putthisinyourspamdatabase.com',
    'spamgourmet.com', 'spamhole.com', 'tempr.email', 'tmpmail.org',
    'trashmail.net', 'trashmailer.com', 'throwawaymail.com', 'tempmailo.com',
    
    # Additional temporary email providers
    '33mail.com', '7tags.com', 'adadres.com', 'agedmail.com', 'amaile.com',
    'anonmails.de', 'antispam.de', 'beefmilk.com', 'binkmail.com', 'bobmail.info',
    'bofthew.com', 'brefmail.com', 'bsnow.net', 'bugmenot.com', 'bumpymail.com',
    'byom.de', 'chammy.info', 'cool.fr.nf', 'courrieltemporaire.com',
    'curryworld.de', 'cust.in', 'dacoolest.com', 'dandikmail.com', 'dayrep.com',
    'deadaddress.com', 'despam.it', 'devnullmail.com', 'dfgh.net', 'digitalsanctuary.com',
    'discard.email', 'discardmail.com', 'discardmail.de', 'disposableaddress.com',
    'disposableemailaddresses.com', 'dispostable.com', 'dodgeit.com', 'dodgit.com',
    'doiea.com', 'donemail.ru', 'dontreg.com', 'dontsendmespam.de', 'drdrb.com',
    'dump-email.info', 'dumpandjunk.com', 'dumpyemail.com', 'e4ward.com',
    'email-away.com', 'email-fake.com', 'emailgo.de', 'emaillime.com',
    'emailmiser.com', 'emailsensei.com', 'emailtemporar.ro', 'emailwarden.com',
    'emailxfer.com', 'emeil.ir', 'emeil.ir', 'emkei.cf', 'evopo.com',
    'explodemail.com', 'fake-box.com', 'fakemail.fr', 'fakemailgenerator.com',
    'fakemailz.com', 'fammix.com', 'fansworldwide.de', 'fastmazda.com',
    'filzmail.com', 'frapmail.com', 'friendlymail.co.uk', 'front14.org',
    'fux0ringduh.com', 'garliclife.com', 'get2mail.fr', 'getairmail.com',
    'getmails.eu', 'getonemail.com', 'ghosttexter.de', 'giantmail.de',
    'girlsundertheinfluence.com', 'gishpuppy.com', 'gmial.com', 'goemailgo.com',
    'gotmail.net', 'gotti.otherinbox.com', 'gowikibooks.com', 'gowikicampus.com',
    'gowikicars.com', 'gowikifilms.com', 'gowikigames.com', 'gowikimusic.com',
    'gowikinetwork.com', 'gowikitravel.com', 'gowikitv.com', 'great-host.in',
    'greensloth.com', 'gsrv.co.uk', 'guerillamail.biz', 'guerillamail.com',
    'guerillamail.de', 'guerillamail.info', 'guerillamail.net', 'guerillamail.org',
    'guerrillamail.com', 'guerrillamailblock.com', 'h8s.org', 'hackthatbit.ch',
    'haltospam.com', 'hatespam.org', 'hidemail.de', 'hidzz.com', 'hmamail.com',
    'hochsitze.com', 'hotpop.com', 'hulapla.de', 'ieatspam.eu', 'ieatspam.info',
    'ihateyoualot.info', 'imails.info', 'inboxclean.com', 'inboxclean.org',
    'incognitomail.org', 'incognitomail.net', 'insorg-mail.info', 'ipoo.org',
    'irish2me.com', 'iwi.net', 'jetable.com', 'jetable.fr.nf', 'jetable.net',
    'jetable.org', 'jnxjn.com', 'jourrapide.com', 'jsrsolutions.com',
    'kasmail.com', 'kaspop.com', 'keepmymail.com', 'killmail.com', 'killmail.net',
    'klassmaster.com', 'klassmaster.net', 'klzlk.com', 'kook.ml', 'koszmail.pl',
    'kurzepost.de', 'l33r.eu', 'lackmail.net', 'lags.us', 'lawlita.com',
    'lazyinbox.com', 'lifebyfood.com', 'link2mail.net', 'litedrop.com',
    'liveradio.tk', 'lol.ovpn.to', 'lookugly.com', 'lopl.co.cc', 'lortemail.dk',
    'lovemeleaveme.com', 'lr78.com', 'lroid.com', 'lukop.dk', 'm21.cc',
    'm4ilweb.info', 'maboard.com', 'mail-temp.com', 'mail.by', 'mail.mezimages.net',
    'mail114.net', 'mail15.com', 'mail2000.ru', 'mail2rss.org', 'mail333.com',
    'mail4trash.com', 'mailbidon.com', 'mailbiz.biz', 'mailblocks.com',
    'mailbucket.org', 'mailcat.biz', 'mailcatch.com', 'mailde.de', 'mailde.info',
    'maildrop.cc', 'maildx.com', 'maileater.com', 'mailexpire.com', 'mailfa.tk',
    'mailfreeonline.com', 'mailguard.me', 'mailin8r.com', 'mailinater.com',
    'mailinator.com', 'mailinator.net', 'mailinator.org', 'mailinator2.com',
    'mailincubator.com', 'mailismagic.com', 'mailita.com', 'mailme.lv',
    'mailmetrash.com', 'mailmoat.com', 'mailms.com', 'mailnull.com',
    'mailorg.org', 'mailpick.biz', 'mailproxsy.com', 'mailquack.com',
    'mailrock.biz', 'mailsac.com', 'mailscrap.com', 'mailseal.de',
    'mailshell.com', 'mailsiphon.com', 'mailslapping.com', 'mailslite.com',
    'mailtemp.info', 'mailtome.de', 'mailtrash.net', 'mailtv.net',
    'mailtv.tv', 'mailzi.com', 'makemetheking.com', 'manybrain.com',
    'mbx.cc', 'meltmail.com', 'messagebeamer.de', 'mezimages.net', 'mierdamail.com',
    'mintemail.com', 'mjukglass.nu', 'moakt.com', 'moburl.com', 'monemail.fr.nf',
    'moo.com', 'moot.es', 'morah.dl.pl', 'msa.minsmail.com', 'mt2014.com',
    'mt2015.com', 'muehlacker.de', 'mvrht.com', 'mycard.net.ua', 'mydomain.com',
    'mypacks.net', 'myspaceinc.com', 'myspaceinc.net', 'myspaceinc.org',
    'mytemp.email', 'mytempemail.com', 'mytrashmail.com', 'neomailbox.com',
    'nepwk.com', 'nervmich.net', 'nervtmich.net', 'netmails.com', 'netmails.net',
    'netzidiot.de', 'neverbox.com', 'nice-4u.com', 'nincsmail.com', 'nnh.com',
    'no-spam.ws', 'nobulk.com', 'noclickemail.com', 'nogmailspam.com',
    'nomail.cf', 'nomail2me.com', 'nomorespamemails.com', 'nospam.ze.tc',
    'nospamfor.us', 'nospamthanks.com', 'notmailinator.com', 'nowmymail.com',
    'nurfuerspam.de', 'nus.edu.sg', 'nwldx.com', 'objectmail.com', 'obobbo.com',
    'odaymail.com', 'odnorazovoe.ru', 'one-time.email', 'onewaymail.com',
    'online.ms', 'oopi.org', 'opayq.com', 'ordinaryamerican.net', 'otherinbox.com',
    'ourklips.com', 'outlawspam.com', 'ovpn.to', 'owlpic.com', 'pancakemail.com',
    'pimpedupmyspace.com', 'pjkh.com', 'plexolan.de', 'poczta.onet.pl',
    'politikerclub.de', 'poofy.org', 'pookmail.com', 'privacy.net', 'privatdemail.net',
    'proxymail.eu', 'prtnx.com', 'putthisinyourspamdatabase.com', 'quickinbox.com',
    'rcpt.at', 'recode.me', 'recursor.net', 'regbypass.com', 'regbypass.comsafe-mail.net',
    'rejectmail.com', 'rhyta.com', 'rklips.com', 'rmqkr.net', 'royal.net',
    'rppkn.com', 'rtrtr.com', 's0ny.net', 'safe-mail.net', 'safetymail.info',
    'safetypost.de', 'sandelf.de', 'saynotospams.com', 'schafmail.de',
    'schmeissweg.tk', 'schrott-email.de', 'secretemail.de', 'secure-mail.biz',
    'selfdestructingmail.com', 'sendspamhere.com', 'sharklasers.com', 'shieldemail.com',
    'shiftmail.com', 'shitmail.me', 'shortmail.net', 'sibmail.com', 'sinnlos-mail.de',
    'skeefmail.com', 'slaskpost.se', 'slipry.net', 'slopsbox.com', 'smellfear.com',
    'snakemail.com', 'sneakemail.com', 'snkmail.com', 'sofimail.com', 'sofort-mail.de',
    'sogetthis.com', 'soodonims.com', 'spam.la', 'spam.su', 'spam4.me', 'spamail.de',
    'spambob.com', 'spambob.net', 'spambob.org', 'spambog.com', 'spambog.de',
    'spambog.net', 'spambog.ru', 'spambox.info', 'spambox.irishspringrealty.com',
    'spambox.us', 'spamcannon.com', 'spamcow.com', 'spamday.com', 'spamex.com',
    'spamfree24.com', 'spamfree24.de', 'spamfree24.eu', 'spamfree24.net',
    'spamfree24.org', 'spamgourmet.com', 'spamherelots.com', 'spamhereplease.com',
    'spamhole.com', 'spamify.com', 'spaminator.de', 'spamkill.info', 'spaml.com',
    'spaml.de', 'spamlot.net', 'spammotel.com', 'spamobox.com', 'spamoff.de',
    'spamslicer.com', 'spamspot.com', 'spamstack.net', 'spamthis.co.uk',
    'spamthisplease.com', 'spamtraps.com', 'spamtroll.net', 'speed.1s.fr',
    'supergreatmail.com', 'supermailer.jp', 'superrito.com', 'superstachel.de',
    'tagyourself.com', 'talkinator.com', 'teewars.org', 'teleosaurs.xyz',
    'teleworm.com', 'temp-mail.org', 'temp-mail.ru', 'tempail.com', 'tempe-mail.com',
    'tempemail.biz', 'tempemail.com', 'tempinbox.co.uk', 'tempinbox.com',
    'tempmail.eu', 'tempmail.it', 'tempmail2.com', 'tempmailer.com', 'tempmailer.de',
    'tempmailo.com', 'tempomail.fr', 'temporarily.de', 'temporarioemail.com.br',
    'tempthe.net', 'tempymail.com', 'thanksnospam.info', 'thankyou2010.com',
    'thisisnotmyrealemail.com', 'throwawayemailaddress.com', 'tilien.com',
    'tmail.ws', 'tmailinator.com', 'toiea.com', 'tradermail.info', 'trash-amil.com',
    'trash-mail.at', 'trash-mail.com', 'trash-mail.de', 'trash2009.com',
    'trashemail.de', 'trashmail.at', 'trashmail.com', 'trashmail.de', 'trashmail.me',
    'trashmail.net', 'trashmail.org', 'trashmail.ws', 'trashmailer.com',
    'trashymail.com', 'trialmail.de', 'trillianpro.com', 'turual.com',
    'twinmail.de', 'tyldd.com', 'uggsrock.com', 'umail.net', 'upliftnow.com',
    'uplipht.com', 'uroid.com', 'us.af', 'venompen.com', 'veryrealemail.com',
    'viditag.com', 'viewcastmedia.com', 'viewcastmedia.net', 'viewcastmedia.org',
    'webemail.me', 'webm4il.info', 'wh4f.org', 'whyspam.me', 'willselfdestruct.com',
    'winemaven.info', 'wronghead.com', 'wuzup.net', 'wuzupmail.net', 'xagloo.com',
    'xemaps.com', 'xents.com', 'xmaily.com', 'xoxy.net', 'yapped.net',
    'yeah.net', 'yep.it', 'yogamaven.com', 'yopmail.com', 'yopmail.fr',
    'yopmail.net', 'youmailr.com', 'ypmail.webnetic.de', 'zippymail.info',
    'zoemail.org', 'zomg.info', 'zxcv.com', 'zxcvbnm.com', 'zzz.com'
}

# Free email providers (optional - can be used for additional filtering)
FREE_EMAIL_PROVIDERS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'icloud.com', 'mail.com', 'protonmail.com', 'zoho.com', 'gmx.com',
    'yandex.com', 'live.com', 'msn.com', 'inbox.com', 'fastmail.com'
}


def is_disposable_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Check if email is from a disposable email provider.
    
    Returns:
        (is_disposable: bool, reason: str or None)
    """
    if not email or '@' not in email:
        return False, None
    
    domain = email.split('@')[1].lower().strip()
    
    # Check against comprehensive disposable domain list
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return True, f"Disposable email provider ({domain}) not allowed"
    
    # Check for common disposable patterns
    disposable_patterns = [
        r'^temp', r'^tmp', r'^throw', r'^fake', r'^spam', r'^trash',
        r'^disposable', r'^dummy', r'^test', r'^noreply', r'^no-reply',
        r'mail$', r'email$', r'inbox$', r'box$'
    ]
    
    for pattern in disposable_patterns:
        if re.search(pattern, domain, re.IGNORECASE):
            return True, f"Email domain matches disposable pattern"
    
    return False, None


def generate_verification_token() -> str:
    """Generate a secure verification token"""
    return secrets.token_urlsafe(32)


def hash_email(email: str) -> str:
    """Create a hash of email for duplicate detection"""
    return hashlib.sha256(email.lower().encode()).hexdigest()


def check_duplicate_email(email: str, ip_address: str, cursor) -> Tuple[bool, Optional[str]]:
    """
    Check if email has been used from a different IP address.
    
    Returns:
        (is_duplicate: bool, reason: str or None)
    """
    email_hash = hash_email(email)
    
    try:
        if DB_TYPE == 'postgresql':
            cursor.execute("""
                SELECT ip_address, created_at, COUNT(*) as usage_count
                FROM email_captures
                WHERE email = %s
                GROUP BY ip_address, created_at
                ORDER BY created_at DESC
                LIMIT 5
            """, (email,))
        else:
            cursor.execute("""
                SELECT ip_address, created_at, COUNT(*) as usage_count
                FROM email_captures
                WHERE email = ?
                GROUP BY ip_address, created_at
                ORDER BY created_at DESC
                LIMIT 5
            """, (email,))
        
        records = cursor.fetchall()
        
        if records:
            # Check if email used from different IP
            unique_ips = set()
            for record in records:
                if isinstance(record, dict):
                    unique_ips.add(record.get('ip_address'))
                else:
                    unique_ips.add(record[0] if len(record) > 0 else None)
            
            unique_ips.discard(None)  # Remove None values
            
            if len(unique_ips) > 1:
                return True, f"Email already used from {len(unique_ips)} different IP addresses"
            
            if ip_address not in unique_ips and len(unique_ips) > 0:
                return True, f"Email already registered from a different location"
        
        return False, None
        
    except Exception as e:
        # If check fails, log but don't block (fail open for legitimate users)
        print(f"⚠️ Error checking duplicate email: {e}")
        return False, None


def validate_email_format(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format using regex.
    
    Returns:
        (is_valid: bool, error_message: str or None)
    """
    if not email:
        return False, "Email is required"
    
    email = email.strip().lower()
    
    # Basic format check
    if '@' not in email or '.' not in email.split('@')[-1]:
        return False, "Invalid email format"
    
    # RFC 5322 compliant regex (simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    # Check length
    if len(email) > 254:  # RFC 5321 limit
        return False, "Email address too long"
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'\.{2,}',  # Multiple consecutive dots
        r'^\.',     # Starts with dot
        r'\.$',     # Ends with dot
        r'@\.',     # @ followed by dot
        r'\.@',     # Dot before @
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, email):
            return False, "Invalid email format"
    
    return True, None

