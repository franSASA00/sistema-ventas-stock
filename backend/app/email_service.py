import requests

from app.config import settings


def enviar_email_reseteo(destinatario: str, nombre: str, link: str) -> bool:
    """Envia el email de recuperacion de contrasena via la API de SendGrid.
    Devuelve True si se envio bien, False si fallo (sin cortar el flujo:
    el endpoint que llama a esto no debe filtrar si un email existe o no)."""
    if not settings.sendgrid_api_key or not settings.email_from:
        print("SENDGRID_API_KEY o EMAIL_FROM no configurados: no se envio el email.")
        return False

    cuerpo_html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #0F5C4C;">Recuperar contrasena</h2>
      <p>Hola {nombre},</p>
      <p>Pediste recuperar tu contrasena en el Sistema de Ventas y Stock. Toca el boton
      de abajo para elegir una nueva. Este link vence en 30 minutos.</p>
      <p style="margin: 24px 0;">
        <a href="{link}" style="background:#0F5C4C; color:white; padding:12px 20px;
        border-radius:8px; text-decoration:none; font-weight:bold;">Elegir nueva contrasena</a>
      </p>
      <p style="color:#888; font-size:13px;">Si no pediste esto, podes ignorar este email.</p>
    </div>
    """

    payload = {
        "personalizations": [{"to": [{"email": destinatario}]}],
        "from": {"email": settings.email_from, "name": "Sistema de Ventas y Stock"},
        "subject": "Recuperar tu contrasena",
        "content": [{"type": "text/html", "value": cuerpo_html}],
    }

    try:
        resp = requests.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            timeout=10,
        )
        return resp.status_code in (200, 201, 202)
    except Exception as e:
        print(f"Error enviando email de reseteo: {e}")
        return False
