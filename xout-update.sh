#!/usr/bin/env bash
# X-OUT: broker.xml Acceptor-Parameter, roles.properties bereinigen, application.yml ergaenzen.
# Idempotent: mehrfaches Ausfuehren aendert nichts mehr. Backups: <datei>.bak (nur beim ersten Lauf).
set -euo pipefail

BROKER=${BROKER:-/etc/xout/activemq-artemis/broker.xml}
ROLES=${ROLES:-/etc/xout/web/roles.properties}
APPYML=${APPYML:-/etc/xout/web/application.yml}

backup() { [ -e "$1.bak" ] || cp -p "$1" "$1.bak"; }

# 1. broker.xml: Parameter an den Acceptor "artemis" haengen
if grep -q 'coreMaxFrameSize=' "$BROKER"; then
  echo "broker.xml: schon gesetzt, uebersprungen"
else
  backup "$BROKER"
  sed -i '/<acceptor name="artemis">/s#</acceptor>#;coreInitialMaxFrameSize=16384;coreMaxFrameSize=524288000</acceptor>#' "$BROKER"
  grep -q 'coreMaxFrameSize=' "$BROKER" || { echo "FEHLER: broker.xml nicht geaendert (Acceptor in einer Zeile?)" >&2; exit 1; }
  echo "broker.xml: angepasst"
fi

# 2. roles.properties: awb, dm, fachexperte, mv, redaktion = AWB, DMS, FB, MV, Redakteure entfernen
backup "$ROLES"
sed -E -i '/^[^#=]+=/{s/=/=,/;s/$/,/;:a;s/,[ ]*(AWB|DMS|FB|MV|Redakteure)[ ]*,/,/;ta;s/=,[ ]*/=/;s/,$//}' "$ROLES"
if sed 's/^[^=]*=//' "$ROLES" | grep -Eq '(^|[, ])(AWB|DMS|FB|MV|Redakteure)([ ,]|$)'; then
  echo "WARNUNG: roles.properties enthaelt noch Rollen (umgebrochene Zeile?) - bitte pruefen" >&2
fi
echo "roles.properties: bereinigt"

# 3. application.yml: Rolle -> Gruppen anhaengen, aber nur wenn der Block noch fehlt
if grep -q '^x-out-authorization:' "$APPYML"; then
  echo "WARNUNG: application.yml hat schon x-out-authorization - bitte manuell zusammenfuehren" >&2
else
  backup "$APPYML"
  [ -z "$(tail -c1 "$APPYML")" ] || echo >> "$APPYML"
  cat >> "$APPYML" <<'EOF'
x-out-authorization:
  operaton:
    groups:
      - id: "awb"
        groups: "FUN_GG_APP_XOUT_TOBI-Zebra,FUN_GG_APP_XOUT-DEG-Support,FUN_GG_APP_XOUT-ADMIN,FUN_GG_APP_XOUT-SupportDesk,FUN_GG_APP_XOUT_TOBI-AWB,FUN_GG_APP_XOUT_TOBI-eAkteDMS"
      - id: "dm"
        groups: "FUN_GG_APP_XOUT_TOBI-Zebra,FUN_GG_APP_XOUT-DEG-Support,FUN_GG_APP_XOUT-ADMIN,FUN_GG_APP_XOUT_TOBI-AWB,FUN_GG_APP_XOUT_TOBI-eAkteDMS"
      - id: "fachexperte"
        groups: "FUN_GG_APP_XOUT_TOBI-Zebra,FUN_GG_APP_XOUT-DEG-Support,FUN_GG_APP_XOUT-ADMIN,FUN_GG_APP_XOUT_TOBI-Fachbereich,FUN_GG_APP_XOUT_TOBI-AWB,FUN_GG_APP_XOUT_TOBI-eAkteDMS"
      - id: "mv"
        groups: "FUN_GG_APP_XOUT_TOBI-Zebra,FUN_GG_APP_XOUT-DEG-Support,FUN_GG_APP_XOUT-ADMIN,FUN_GG_APP_XOUT_TOBI-ZMV,FUN_GG_APP_XOUT_TOBI-AWB,FUN_GG_APP_XOUT_TOBI-eAkteDMS"
      - id: "redaktion"
        groups: "FUN_GG_APP_XOUT_TOBI-Redakteure,FUN_GG_APP_XOUT_TOBI-Zebra,FUN_GG_APP_XOUT-DEG-Support,FUN_GG_APP_XOUT-ADMIN,FUN_GG_APP_XOUT_TOBI-AWB,FUN_GG_APP_XOUT_TOBI-eAkteDMS"
EOF
  echo "application.yml: Block angehaengt"
fi
