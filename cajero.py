
import json
import os
import re
import tempfile
from datetime import datetime


# Config / constantes

DATA_FILE = "usuarios_pulgarcito.json"
BACKUP_SUFFIX = ".bak"
FECHA_FMT = "%Y-%m-%d %H:%M:%S"
SALDO_MINIMO = 50000
MULTIPLO = 10000


# Utilidades

def ahora():
    return datetime.now().strftime(FECHA_FMT)

def safe_int(s):
    """Convierte a int de forma segura, lanza ValueError si no se puede."""
    try:
        return int(str(s).strip())
    except Exception:
        raise ValueError("No es entero valido")

def es_multiplo_10000_valido(monto):
    """Verifica que monto sea entero positivo y multiplo de 10000."""
    try:
        m = safe_int(monto)
    except ValueError:
        return False
    return m > 0 and (m % MULTIPLO == 0)


# Persistencia segura

def backup_si_existe(path):
    """Hace backup simple del archivo si existe."""
    try:
        if os.path.exists(path):
            bak = path + BACKUP_SUFFIX
            # sobreescribe bak si ya existe
            try:
                os.replace(path, bak)
            except Exception:
                # si falla, intentamos copiar
                with open(path, "rb") as origen, open(bak, "wb") as destino:
                    destino.write(origen.read())
    except Exception:
        # no interrumpir por fallo de backup
        pass

def escribir_json_atomo(path, data):
    """Escribe JSON de forma atomica (tmp file y replace)."""
    dirn = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dirn, prefix=".tmp_", suffix=".json")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def cargar_datos():
    """Carga usuarios desde DATA_FILE; hace backup si el json esta corrupto."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("Formato invalido")
        # normalizar campos: asegurar claves monetarias como int
        for ced, u in data.items():
            for campo in ("saldo_capital", "saldo_prestamo", "deuda"):
                if campo in u:
                    try:
                        u[campo] = int(u[campo])
                    except Exception:
                        u[campo] = 0
            # operaciones: asegurar monto como int cuando sea posible
            ops = u.get("operaciones", [])
            for op in ops:
                if 'monto' in op:
                    try:
                        op['monto'] = int(op['monto'])
                    except Exception:
                        # mantener el valor que venga para traza
                        pass
        return data
    except Exception:
        try:
            backup_si_existe(DATA_FILE)
        except Exception:
            pass
        return {}

def guardar_datos(data):
    """Guarda datos con escritura atomica y sin corromper si hay fallos."""
    try:
        escribir_json_atomo(DATA_FILE, data)
    except Exception as e:
        print("[WARN] no se pudo guardar datos:", e)


# Validaciones

def validar_email_com(email):
    """Valida que el email tenga formato y termine en .com"""
    if not isinstance(email, str):
        return False
    email = email.strip().lower()
    # exige terminacion .com
    patron = r'^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.com$'
    return re.match(patron, email) is not None

def nombre_valido(txt):
    """Verifica nombre/apellidos (solo letras y espacios)."""
    if not isinstance(txt, str) or not txt.strip():
        return False
    t = txt.strip()
    return t.replace(" ", "").isalpha()

def cedula_unica(data, cedula):
    return cedula not in data

def email_unico(data, email, cedula_actual=None):
    e = (email or "").strip().lower()
    for ced, u in data.items():
        if ced == cedula_actual:
            continue
        if u.get("email", "").strip().lower() == e:
            return False
    return True


# Registro de operaciones 

def registrar_operacion(data, cedula, tipo, monto, estado="OK", descripcion="", destinatario=None):
    """
    Agrega una operacion con campos uniformes:
    fecha, tipo, monto, estado (OK/ERROR), descripcion, destinatario(optional)
    """
    op = {
        "fecha": ahora(),
        "tipo": tipo,
        "monto": monto,
        "estado": estado,
        "descripcion": descripcion
    }
    if destinatario:
        op["destinatario"] = destinatario
    data.setdefault(cedula, {}).setdefault("operaciones", []).append(op)
    # guardamos cada vez para persistencia inmediata
    guardar_datos(data)


# Funciones principales 


def registrar_usuario(data):
    print("\n# registro")
    while True:
        ced = input("Cedula (solo numeros): ").strip()
        if not ced.isdigit():
            print("cedula invalida, solo numeros")
            continue
        if not cedula_unica(data, ced):
            print("esa cedula ya existe")
            continue
        break

    # nombre/apellidos
    while True:
        nombre = input("Nombre: ").strip()
        if not nombre_valido(nombre):
            print("nombre invalido")
            continue
        break
    while True:
        apellidos = input("Apellidos: ").strip()
        if not nombre_valido(apellidos):
            print("apellidos invalidos")
            continue
        break

    # fecha nacimiento y edad
    while True:
        fn = input("Fecha nacimiento (YYYY-MM-DD): ").strip()
        try:
            fecha = datetime.strptime(fn, "%Y-%m-%d")
            hoy = datetime.now()
            edad = hoy.year - fecha.year - ((hoy.month, hoy.day) < (fecha.month, fecha.day))
            if edad < 18:
                print("debe ser mayor de 18")
                continue
            break
        except Exception:
            print("formato fecha invalido")
            continue

    # genero y estado civil
    while True:
        genero = input("Genero (M/F/O): ").strip().upper()
        if genero not in ("M", "F", "O"):
            print("opcion invalida")
            continue
        break
    while True:
        estado = input("Estado civil (U/S/C/D): ").strip().upper()
        if estado not in ("U", "S", "C", "D"):
            print("opcion invalida")
            continue
        break

    # email (termina en .com y unico)
    while True:
        email = input("Email (termina en .com): ").strip().lower()
        if not validar_email_com(email):
            print("email invalido, debe terminar en .com y ser formato valido")
            continue
        if not email_unico(data, email):
            print("email ya registrado")
            continue
        break

    usuario = input("Usuario (login): ").strip() or "usuario_default"

    # clave simple con input (no getpass segun requerimiento)
    while True:
        clave = input("Clave (min 4 chars): ").strip()
        if len(clave) < 4:
            print("clave corta")
            continue
        break

    # saldo inicial: >= SALDO_MINIMO y multiplo
    while True:
        entrada = input(f"Saldo inicial (min {SALDO_MINIMO}, multiplo {MULTIPLO}): ").strip()
        try:
            monto = safe_int(entrada)
        except ValueError:
            print("saldo invalido")
            continue
        if monto < SALDO_MINIMO:
            print("saldo por debajo del minimo")
            continue
        if monto % MULTIPLO != 0:
            print("saldo debe ser multiplo de 10000")
            continue
        break

    # crear usuario
    data[ced] = {
        "cedula": ced,
        "nombre": nombre,
        "apellidos": apellidos,
        "fecha_nacimiento": fn,
        "edad": edad,
        "genero": genero,
        "estado_civil": estado,
        "email": email,
        "fecha_apertura": ahora(),
        "usuario": usuario,
        "clave": clave,
        "saldo_capital": monto,
        "saldo_prestamo": 0,
        "deuda": 0,
        "operaciones": []
    }

    registrar_operacion(data, ced, "APERTURA", monto, "OK", "Apertura de cuenta")
    print("usuario registrado correctamente")

def iniciar_sesion(data):
    print("\n# inicio de sesion")
    ced = input("Cedula: ").strip()
    if ced not in data:
        print("usuario no encontrado")
        return None
    usuario_ing = input("Usuario: ").strip()
    clave = input("Clave: ").strip()
    u = data[ced]
    if u.get("usuario") == usuario_ing and u.get("clave") == clave:
        print(f"Bienvenido {u.get('nombre')} {u.get('apellidos')}")
        return ced
    else:
        print("credenciales incorrectas")
        # registramos intento fallido como consulta de seguridad (no sensible)
        registrar_operacion(data, ced, "LOGIN_INTENTO", 0, "ERROR", "Credenciales incorrectas")
        return None


# Operaciones: depositar, retirar, giro, prestamo, abonar

def depositar(data, ced):
    u = data[ced]
    print("\n# deposito")
    entrada = input("Monto a depositar (multiplo 10000): ").strip()
    try:
        monto = safe_int(entrada)
    except ValueError:
        print("monto invalido")
        registrar_operacion(data, ced, entrada, "ERROR", "Monto no numerico")
        return
    if monto <= 0 or monto % MULTIPLO != 0:
        print("monto debe ser positivo y multiplo de 10000")
        registrar_operacion(data, ced, monto, "ERROR", "Monto no multiplo o no positivo")
        return

    # si hay deuda, abonar primero
    if u["deuda"] > 0:
        deuda = u["deuda"]
        if monto >= deuda:
            excedente = monto - deuda
            u["deuda"] = 0
            u["saldo_prestamo"] = 0
            if excedente > 0:
                u["saldo_capital"] += excedente
            registrar_operacion(data, ced, monto, "OK", f"Pago deuda {deuda}; excedente {excedente}")
            print("deuda saldada; excedente agregado al capital si hubo")
        else:
            u["deuda"] -= monto
            u["saldo_prestamo"] = max(0, u["saldo_prestamo"] - monto)
            registrar_operacion(data, ced, monto, "OK", f"Abono a deuda; resta {u['deuda']}")
            print(f"abono realizado; deuda restante {u['deuda']}")
    else:
        u["saldo_capital"] += monto
        registrar_operacion(data, ced, monto, "OK", "Deposito a capital")
        print("deposito exitoso")
    guardar_datos(data)

def retirar(data, ced):
    u = data[ced]
    print("\n# retiro")
    if u["deuda"] > 0:
        print("no puede retirar con deuda pendiente")
        registrar_operacion(data, ced, 0, "ERROR", "Intento retiro con deuda")
        return
    entrada = input("Monto a retirar (multiplo 10000): ").strip()
    try:
        monto = safe_int(entrada)
    except ValueError:
        print("monto invalido")
        registrar_operacion(data, ced, entrada, "ERROR", "Monto no numerico")
        return
    if monto <= 0 or monto % MULTIPLO != 0:
        print("monto invalido o no multiplo")
        registrar_operacion(data, ced, monto, "ERROR", "Monto no multiplo o no positivo")
        return
    if monto > u["saldo_capital"]:
        print("saldo insuficiente")
        registrar_operacion(data, ced, monto, "ERROR", "Saldo insuficiente")
        return
    if u["saldo_capital"] - monto < SALDO_MINIMO:
        print(f"debe dejar saldo minimo {SALDO_MINIMO}")
        registrar_operacion(data, ced, monto, "ERROR", "Bajo saldo minimo")
        return
    u["saldo_capital"] -= monto
    registrar_operacion(data, ced, monto, "OK", "Retiro exitoso")
    print("retiro realizado")
    guardar_datos(data)

def solicitar_prestamo(data, ced):
    u = data[ced]
    print("\n# solicitud de prestamo")
    if u["deuda"] > 0:
        print("no puede pedir prestamo con deuda vigente")
        registrar_operacion(data, ced, 0, "ERROR", "Intento prestamo con deuda")
        return
    maximo = u["saldo_capital"] * 4
    print(f"prestamo maximo: {maximo}")
    entrada = input("Monto prestamo (multiplo 10000): ").strip()
    try:
        monto = safe_int(entrada)
    except ValueError:
        print("monto invalido")
        registrar_operacion(data, ced, entrada, "ERROR", "Monto no numerico")
        return
    if monto <= 0 or monto % MULTIPLO != 0:
        print("monto invalido o no multiplo")
        registrar_operacion(data, ced, monto, "ERROR", "Monto no multiplo o no positivo")
        return
    if monto > maximo:
        print("monto excede el maximo permitido")
        registrar_operacion(data, ced, monto, "ERROR", "Excede maximo")
        return
    u["saldo_prestamo"] += monto
    u["deuda"] += monto
    u["saldo_capital"] += monto  # acreditado al capital
    registrar_operacion(data, ced, monto, "OK", "Prestamo aprobado y acreditado")
    print("prestamo aprobado")
    guardar_datos(data)

def realizar_giro(data, ced):
    u = data[ced]
    print("\n# giro a otra cuenta")
    if u["deuda"] > 0:
        print("no puede hacer giros con deuda pendiente")
        registrar_operacion(data, ced, 0, "ERROR", "Intento giro con deuda")
        return
    destino = input("Cuenta destino (cedula): ").strip()
    if destino == ced:
        print("no puede girar a la misma cuenta")
        registrar_operacion(data, ced, 0, "ERROR", "Giro a misma cuenta")
        return
    if destino not in data:
        print("cuenta destino no existe")
        registrar_operacion(data, ced, 0, "ERROR", "Destino no existe")
        return
    entrada = input("Monto giro (multiplo 10000): ").strip()
    try:
        monto = safe_int(entrada)
    except ValueError:
        print("monto invalido")
        registrar_operacion(data, ced, entrada, "ERROR", "Monto no numerico")
        return
    if monto <= 0 or monto % MULTIPLO != 0:
        print("monto no valido o no multiplo")
        registrar_operacion(data, ced, monto, "ERROR", "Monto no multiplo")
        return
    if monto > u["saldo_capital"]:
        print("saldo insuficiente")
        registrar_operacion(data, ced, monto, "ERROR", "Saldo insuficiente")
        return
    if u["saldo_capital"] - monto < SALDO_MINIMO:
        print("no puede dejar la cuenta por debajo del saldo minimo")
        registrar_operacion(data, ced, monto, "ERROR", "Bajo saldo minimo post-giro")
        return
    # ejecutar giro
    u["saldo_capital"] -= monto
    data[destino]["saldo_capital"] = data[destino].get("saldo_capital", 0) + monto
    registrar_operacion(data, ced, monto, "OK", f"Giro a {destino}", destinatario=destino)
    registrar_operacion(data, destino, monto, "OK", f"Recepcion giro desde {ced}", destinatario=ced)
    print("giro efectuado")
    guardar_datos(data)

def abonar_prestamo(data, ced):
    u = data[ced]
    print("\n# abonar prestamo")
    if u["deuda"] <= 0:
        print("no tiene deuda")
        return
    entrada = input("Monto abono (multiplo 10000): ").strip()
    try:
        monto = safe_int(entrada)
    except ValueError:
        print("monto invalido")
        registrar_operacion(data, ced, entrada, "ERROR", "Monto no numerico")
        return
    if monto <= 0 or monto % MULTIPLO != 0:
        print("monto invalido o no multiplo")
        registrar_operacion(data, ced, monto, "ERROR", "Monto no multiplo o no positivo")
        return
    if monto > u.get("saldo_capital", 0) + 0:
        pass
    deuda_prev = u["deuda"]
    if monto >= deuda_prev:
        excedente = monto - deuda_prev
        u["deuda"] = 0
        u["saldo_prestamo"] = 0
        if excedente > 0:
            u["saldo_capital"] += excedente
        registrar_operacion(data, ced, monto, "OK", f"Pago total deuda {deuda_prev}; excedente {excedente}")
        print("deuda pagada, excedente (si hubo) agregado al capital")
    else:
        u["deuda"] -= monto
        u["saldo_prestamo"] = max(0, u["saldo_prestamo"] - monto)
        registrar_operacion(data, ced, monto, "OK", f"Abono parcial; resta {u['deuda']}")
        print("abono parcial realizado")
    guardar_datos(data)


# Consultas / Historial

def consultar_saldo(data, ced):
    u = data[ced]
    print("\n# consulta saldo")
    print("Saldo capital:", u.get("saldo_capital", 0))
    print("Saldo prestamo:", u.get("saldo_prestamo", 0))
    print("Deuda pendiente:", u.get("deuda", 0))
    registrar_operacion(data, ced, 0, "OK", "Consulta de saldo")

def mostrar_historial(data, ced):
    u = data[ced]
    ops = u.get("operaciones", [])
    if not ops:
        print("No hay operaciones registradas.")
        return
    # orden por fecha descendente; si falla el parse, usamos orden inverso
    try:
        ops_sorted = sorted(ops, key=lambda x: datetime.strptime(x.get("fecha", ""), FECHA_FMT), reverse=True)
    except Exception:
        ops_sorted = list(reversed(ops))
    print("\n# historial (mas reciente primero)")
    for i, op in enumerate(ops_sorted, start=1):
        monto = op.get("monto")
        print(f"{i}. [{op.get('fecha')}] {op.get('tipo')} - {monto} - {op.get('estado')}")
        if op.get("descripcion"):
            print("     ", op.get("descripcion"))
        if op.get("destinatario"):
            print("     destinatario:", op.get("destinatario"))

def filtrar_por_tipo(data, ced):
    u = data[ced]
    print("\n# filtrar por tipo")
    print("1. Depositos")
    print("2. Retiros")
    print("3. Giros")
    print("4. Prestamos")
    print("5. Consultas")
    op = input("Elige: ").strip()
    mapa = {'1': "DEPÓSITO", '2': "RETIRO", '3': "GIRO", '4': "PRÉSTAMO", '5': "CONSULTA"}
    tipo = mapa.get(op)
    if not tipo:
        print("opcion invalida")
        return
    ops = [x for x in u.get("operaciones", []) if x.get("tipo") == tipo]
    try:
        ops.sort(key=lambda x: datetime.strptime(x.get("fecha", ""), FECHA_FMT), reverse=True)
    except Exception:
        pass
    if not ops:
        print("No hay operaciones de este tipo.")
        return
    # paginacion sencilla
    idx = 0
    per = 5
    while idx < len(ops):
        bloque = ops[idx: idx+per]
        for opx in bloque:
            print(opx.get("fecha"), "-", opx.get("tipo"), "-", opx.get("monto"), "-", opx.get("estado"))
            if opx.get("descripcion"):
                print("   ", opx.get("descripcion"))
        idx += per
        cont = input("Enter para ver mas o 'q' para salir: ").strip().lower()
        if cont == 'q':
            break


# Actualizar datos

def actualizar_usuario(data, ced):
    u = data[ced]
    print("\n# actualizar datos")
    print("1. Nombre")
    print("2. Apellidos")
    print("3. Email")
    print("4. Usuario")
    print("5. Clave")
    print("0. Volver")
    op = input("Elige: ").strip()
    if op == '1':
        nuevo = input("Nuevo nombre: ").strip()
        if nombre_valido(nuevo):
            u["nombre"] = nuevo
            print("nombre actualizado")
        else:
            print("nombre invalido")
    elif op == '2':
        nuevo = input("Nuevos apellidos: ").strip()
        if nombre_valido(nuevo):
            u["apellidos"] = nuevo
            print("apellidos actualizados")
        else:
            print("apellidos invalidos")
    elif op == '3':
        nuevo = input("Nuevo email (.com): ").strip().lower()
        if not validar_email_com(nuevo):
            print("email invalido")
            return
        if not email_unico(data, nuevo, ced):
            print("email ya registrado por otro usuario")
            return
        u["email"] = nuevo
        print("email actualizado")
    elif op == '4':
        nuevo = input("Nuevo usuario: ").strip()
        if nuevo:
            u["usuario"] = nuevo
            print("usuario actualizado")
        else:
            print("usuario invalido")
    elif op == '5':
        nuevo = input("Nueva clave (min 4): ").strip()
        if len(nuevo) >= 4:
            u["clave"] = nuevo
            print("clave actualizada")
        else:
            print("clave corta")
    elif op == '0':
        return
    else:
        print("opcion invalida")
    guardar_datos(data)

# Menu usuario

def menu_usuario(data, ced):
    while True:
        print("\n--- MENU USUARIO ---")
        print("1. Consultar saldo")
        print("2. Depositar")
        print("3. Retirar")
        print("4. Solicitar prestamo")
        print("5. Realizar giro")
        print("6. Abonar prestamo")
        print("7. Ver historial")
        print("8. Filtrar por tipo")
        print("9. Actualizar datos")
        print("10. Cerrar sesion")
        op = input("Elige: ").strip()
        if op == '1':
            consultar_saldo(data, ced)
        elif op == '2':
            depositar(data, ced)
        elif op == '3':
            retirar(data, ced)
        elif op == '4':
            solicitar_prestamo(data, ced)
        elif op == '5':
            realizar_giro(data, ced)
        elif op == '6':
            abonar_prestamo(data, ced)
        elif op == '7':
            mostrar_historial(data, ced)
        elif op == '8':
            filtrar_por_tipo(data, ced)
        elif op == '9':
            actualizar_usuario(data, ced)
        elif op == '10':
            print("cerrando sesion")
            break
        else:
            print("opcion invalida")


# Menu principal

def menu_principal():
    data = cargar_datos()
    print("\n--- Cajero Pulgarcito ---")
    while True:
        print("\n1. Registrar usuario")
        print("2. Iniciar sesion")
        print("3. Salir")
        op = input("Elige: ").strip()
        if op == '1':
            registrar_usuario(data)
        elif op == '2':
            ced = iniciar_sesion(data)
            if ced:
                menu_usuario(data, ced)
        elif op == '3':
            print("gracias por usar cajero, adios")
            break
        else:
            print("opcion no valida")

if __name__ == "__main__":
    menu_principal()
