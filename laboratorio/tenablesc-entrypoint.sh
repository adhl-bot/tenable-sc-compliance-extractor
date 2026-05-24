#!/usr/bin/bash
set -u

DATE=$(/usr/bin/cat /.build_date 2>/dev/null || /usr/bin/echo "unknown")
RUNDATE=$(/usr/bin/date)

/usr/bin/echo ""
/usr/bin/echo "----------------------------"
/usr/bin/echo "Labbox (Tenable.sc) Starting"
/usr/bin/echo "----------------------------"
/usr/bin/echo "Image v2.0 built on $DATE"
/usr/bin/echo "Container started on $RUNDATE"
/usr/bin/echo "----------------------------"

if ! /usr/bin/getent group tns >/dev/null 2>&1; then
  /usr/sbin/groupadd -g 250 tns
fi
if ! /usr/bin/id tns >/dev/null 2>&1; then
  /usr/sbin/useradd -u 250 -g tns -d /opt/sc -s /bin/bash tns
fi
if [ "$(/usr/bin/id -u tns)" != "250" ] || [ "$(/usr/bin/id -g tns)" != "250" ]; then
  /usr/bin/echo "ERROR: tns must be uid/gid 250" >&2
  exit 2
fi

if ! /usr/bin/locale -a | /usr/bin/grep -Eiq '^en_US\.(utf8|UTF-8)$'; then
  if /usr/bin/command -v dnf >/dev/null 2>&1; then
    /usr/bin/dnf install -y glibc-langpack-en glibc-locale-source >/tmp/tenablesc-locale-install.log 2>&1 || {
      /usr/bin/cat /tmp/tenablesc-locale-install.log >&2
      exit 3
    }
  fi
  /usr/bin/localedef -i en_US -f UTF-8 en_US.UTF-8 || true
fi

# Keep the upstream Labbox update path intact.
/usr/bin/chmod +x /labbox/update.sh
/usr/bin/bash /labbox/update.sh

# Install the lab-specific supervisor config after the upstream update, because
# update.sh rewrites /etc/supervisord-tenablesc.conf from /labbox.
if [ -f /opt/holcim/tenablesc-supervisord.conf ]; then
  /usr/bin/cp -f /opt/holcim/tenablesc-supervisord.conf /tmp/tenablesc-supervisord.conf
  /usr/bin/dos2unix -q /tmp/tenablesc-supervisord.conf 2>/dev/null || true
  /usr/bin/cp -f /tmp/tenablesc-supervisord.conf /etc/supervisord-tenablesc.conf
  /usr/bin/echo "Installed Holcim supervisor config with internal service autostart."
fi

/usr/bin/mkdir -p /opt/sc/admin/logs /opt/sc/admin/logs/services /opt/sc/data/postgresql /opt/sc/data/redis
if /usr/bin/id tns >/dev/null 2>&1; then
  /usr/bin/chown -R tns:tns /opt/sc/admin/logs /opt/sc/data/postgresql /opt/sc/data/redis
fi

/usr/bin/chmod +x /running.sh
exec /usr/bin/bash /running.sh
