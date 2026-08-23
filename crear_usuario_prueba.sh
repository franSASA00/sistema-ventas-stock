curl -s -X POST http://127.0.0.1:8000/usuarios \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"nombre":"Usuario Prueba Email","username":"pruebaemail","password":"1234","rol":"pos","email":"fransansal-094@outlook.com","sucursal_ids":[]}'
