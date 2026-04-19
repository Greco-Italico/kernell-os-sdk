# Security Policy — Kernell OS SDK

## Versiones con soporte activo de seguridad

| Versión | Soporte     |
|---------|-------------|
| 1.0.x   | ✅ Activo   |
| < 1.0   | ❌ Sin soporte |

## Reportar una vulnerabilidad

**⚠️ NO abras un issue público en GitHub para reportar vulnerabilidades de seguridad.**

Hacerlo expone a todos los usuarios del SDK antes de que exista un parche disponible.

### Canal oficial de reporte

📧 **security@kernell.site**

PGP Fingerprint (para comunicaciones sensibles):
```
[Agrega aquí tu PGP fingerprint cuando configures el buzón de seguridad]
```

### Qué incluir en tu reporte

1. **Descripción** de la vulnerabilidad y su impacto potencial
2. **Pasos para reproducirla** (PoC si es posible — no lo publiques aún)
3. **Versiones afectadas**
4. **Posible solución** (opcional pero muy apreciada)

### Nuestros compromisos

| Compromiso | Tiempo |
|---|---|
| Acuse de recibo | ≤ 48 horas |
| Evaluación de impacto | ≤ 7 días |
| Parche listo | ≤ 14 días (crítico), ≤ 30 días (alto), ≤ 90 días (medio) |
| CVE asignado | Al publicar el parche |

### Política de divulgación

Seguimos **Coordinated Vulnerability Disclosure (CVD)**:

- Pedimos un embargo de **90 días** desde el reporte hasta la divulgación pública.
- Esto permite que los usuarios actualicen antes de que el exploit sea público.
- Si el parche está listo antes, coordinamos la divulgación anticipada contigo.
- Si el investigador lo desea, publicamos un agradecimiento en el CHANGELOG y/o CVE.

### Hall of Fame

Agradecemos a los investigadores que han contribuido a la seguridad del SDK:
*(Próximamente)*

---

## Configuración de seguridad recomendada para producción

```bash
# 1. Usar siempre la última versión
pip install kernell-os-sdk --upgrade

# 2. Verificar el hash del paquete
pip install kernell-os-sdk --require-hashes -r requirements.lock

# 3. Ejecutar en entorno aislado
python -m venv .venv && source .venv/bin/activate
pip install kernell-os-sdk

# 4. No ejecutar como root
# El SDK rechazará el inicio si detecta que corre como UID 0
```

## Divulgaciones anteriores

*(Sin CVEs registrados hasta la fecha)*
