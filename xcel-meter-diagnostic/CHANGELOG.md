# Changelog

## 0.3.1

- Added compatibility for Itron meters requiring legacy TLS server renegotiation support with modern OpenSSL.
- Retains TLS 1.2 and the IEEE 2030.5 cipher configuration.

## 0.3.0

- First Home Assistant-native diagnostic app.
- Read-only discovery of legacy Xcel iTron MQTT app identity.
- Certificate-derived LFDI validation.
- Direct IEEE 2030.5 meter discovery and core reading validation.
- No MQTT publishing and no certificate mutation.

