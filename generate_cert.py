"""
Erzeugt ein selbstsigniertes HTTPS-Zertifikat (cert.pem + key.pem) für
Duck-Tape, damit der QR-Code-Kamera-Scanner auch von anderen Geräten im
Netzwerk aus funktioniert (Browser erlauben Kamerazugriff nur über HTTPS
oder localhost, nicht über eine normale http://-Netzwerk-IP).

Einmalig ausführen (und erneut, falls sich die lokale Netzwerk-IP dieses
PCs ändert, z.B. nach einem Neustart mit neuer DHCP-Adresse):

    python generate_cert.py

Das Zertifikat wird automatisch für folgende Adressen gültig gemacht:
    - localhost / 127.0.0.1
    - die aktuell erkannte(n) lokale(n) Netzwerk-IP(s) dieses PCs

WICHTIG: Da es sich um ein SELBSTSIGNIERTES Zertifikat handelt (nicht von
einer offiziellen Zertifizierungsstelle ausgestellt), zeigen Browser beim
ersten Aufruf eine Sicherheitswarnung ("Nicht sicher" / "Verbindung ist
nicht privat"). Das ist normal und erwartet - auf jedem Gerät einmalig auf
"Erweitert" -> "Trotzdem fortfahren" klicken, danach funktioniert alles
inklusive Kamera.
"""

import datetime
import ipaddress
import socket
from datetime import timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def get_local_ips():
    """Best-effort attempt to find every local IPv4 address of this PC."""
    ips = {"127.0.0.1"}

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ":" not in ip:  # nur IPv4, keine IPv6-Adressen
                ips.add(ip)
    except Exception:
        pass

    # Zusätzlicher Trick: ermittelt die IP, die für ausgehende Verbindungen
    # genutzt würde - meist die "echte" LAN-IP, auch wenn mehrere Netzwerk-
    # karten vorhanden sind.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass

    return sorted(ips)


def main():
    ips = get_local_ips()
    print("Erzeuge Zertifikat für folgende Adressen:")
    for ip in ips:
        print(" -", ip)
    print(" - localhost")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Duck-Tape lokale Reparaturdatenbank"),
    ])

    san_entries = [x509.DNSName("localhost")]
    san_entries += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips]

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(timezone.utc))
        .not_valid_after(datetime.datetime.now(timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .sign(key, hashes.SHA256())
    )

    with open("cert.pem", "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open("key.pem", "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    print("\nFertig! 'cert.pem' und 'key.pem' wurden in diesem Ordner erstellt.")
    print("Starte die App jetzt (neu) mit 'python app.py' - sie läuft dann")
    print("automatisch über HTTPS. Beim ersten Aufruf auf jedem Gerät einmalig")
    print("die Sicherheitswarnung des Browsers bestätigen (siehe README.md).")


if __name__ == "__main__":
    main()
