import streamlit as st
import sqlite3
import pandas as pd
from datetime import date

# Configuración de página
st.set_page_config(page_title="Fashion Store - Inventario", layout="wide")
st.title("🧵 FASHION STORE - Control de Inventario")

# Conexión única a la base de datos de tu script
DB_PATH = 'siga_clase.db'

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# Inicializar la base de datos y vistas si no existen (usando tu misma estructura)
def inicializar_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        ciudad TEXT
    );
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        categoria TEXT NOT NULL,
        precio REAL NOT NULL CHECK (precio > 0),
        id_proveedor INTEGER,
        fecha_vencimiento TEXT,
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id)
    );
    CREATE TABLE IF NOT EXISTS movimientos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_producto INTEGER NOT NULL,
        tipo TEXT NOT NULL CHECK (tipo IN ('entrada','salida')),
        cantidad INTEGER NOT NULL CHECK (cantidad > 0),
        fecha TEXT NOT NULL,
        FOREIGN KEY (id_producto) REFERENCES productos(id)
    );
    
    DROP VIEW IF EXISTS vw_inventario;
    CREATE VIEW vw_inventario AS
    SELECT p.id, p.nombre, p.categoria, p.precio,
           COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE -m.cantidad END), 0) AS stock
    FROM productos p
    LEFT JOIN movimientos m ON m.id_producto = p.id
    GROUP BY p.id, p.nombre, p.categoria, p.precio;
    """)
    
    # Verificar si hay datos iniciales, de lo contrario insertar muestras
    cursor.execute("SELECT COUNT(*) FROM proveedores")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
        INSERT INTO proveedores (nombre, ciudad) VALUES
         ('fartelas ', 'cali'), ('induboton ', 'yumbo'), ('insumos_valle', NULL), ('distribuidora_textil', 'bogota');
        
        INSERT INTO productos (nombre, categoria, precio, id_proveedor, fecha_vencimiento) VALUES
         ('telas_lino ' , 'rollo', 600000, 1, '2028-03-15'),
         ('telas_algodon ' , 'rollo', 700000, 1, '2028-05-12'),
         ('telas_seda ' , 'rollo', 800000, 4, '2027-12-30'),
         ('hilos ' , 'carreto', 10000, 2, '2029-12-10'),
         ('cremalleras  ' , 'caja', 40000, 3, NULL),
         ('botones ',  'caja', 20000, 2, NULL ),
         ('cintas ' , 'carreto', 200000, 3, '2027-12-20' ),
         ('herrajes ' , 'caja', 100000, 3, NULL ),
         ('resortes ' , 'carreto', 200000, 3, '2027-12-20' );

        INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES
         (1,'entrada',100,'2026-09-01'),(2,'entrada',80,'2026-09-01'),(3,'entrada',40,'2026-09-02'),
         (4,'entrada',60,'2026-09-02'),(5,'entrada',50,'2026-09-03'),(6,'entrada',5,'2026-09-03'),
         (7,'entrada',30,'2026-09-05'),(8,'entrada',200,'2026-09-05'),(9,'entrada',50,'2026-09-06'),
         (1,'salida',30,'2026-09-10'),(2,'salida',20,'2026-09-12'),(3,'salida',15,'2026-09-15'),
         (4,'salida',25,'2026-09-18'),(8,'salida',120,'2026-09-20'),(1,'salida',25,'2026-09-25'),
         (5,'salida',10,'2026-09-26'),(9,'salida',15,'2026-09-28'),(7,'salida',10,'2026-10-02'),
         (1,'salida',10,'2026-10-03');
        """)
    conn.commit()
    conn.close()

inicializar_db()

# Funciones auxiliares utilizando la lógica del script
def existe_producto(id_producto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM productos WHERE id = ?", (id_producto,))
    res = cursor.fetchone() is not None
    conn.close()
    return res

def registrar_movimiento(id_producto, tipo, cantidad, fecha):
    if not isinstance(cantidad, int) or cantidad <= 0:
        return False, "La cantidad debe ser un número entero mayor que 0."
    if not existe_producto(id_producto):
        return False, f"El producto con ID {id_producto} no existe."
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if tipo == 'salida':
        cursor.execute("SELECT stock FROM vw_inventario WHERE id = ?", (id_producto,))
        stock_row = cursor.fetchone()
        stock = stock_row[0] if stock_row else 0
        if cantidad > stock:
            conn.close()
            return False, f"Stock insuficiente: hay {stock} y se piden {cantidad}."
            
    try:
        cursor.execute(
            "INSERT INTO movimientos (id_producto, tipo, cantidad, fecha) VALUES (?, ?, ?, ?)",
            (id_producto, tipo, cantidad, fecha)
        )
        conn.commit()
        conn.close()
        return True, f"{tipo.capitalize()} registrada: {cantidad} unidades del producto ID {id_producto}."
    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Error al guardar: {e}"

# 4 PESTAÑAS
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard y Alertas", 
    "📥 Registrar Movimientos", 
    "🔍 Consultar Inventario", 
    "🗄️ Base de Datos"
])

# PESTAÑA 1: Dashboard y Alertas
with tab1:
    st.header("Indicadores Generales del Inventario")
    conn = get_connection()
    df_inv = pd.read_sql_query("SELECT * FROM vw_inventario", conn)
    conn.close()
    
    total_referencias = len(df_inv)
    total_unidades = int(df_inv['stock'].sum())
    valor_total_inv = sum(df_inv['stock'] * df_inv['precio'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Referencias", f"{total_referencias} ítems")
    col2.metric("Materiales Disponibles (Stock)", f"{total_unidades} unidades")
    col3.metric("Valorización Total de Inventario", f"${valor_total_inv:,.2f} COP")
    
    st.subheader("⚠️ Alertas de Reposición (Stock Bajo < 30 unidades)")
    alertas_df = df_inv[df_inv['stock'] < 30]
    if not alertas_df.empty:
        st.warning(f"Se encontraron {len(alertas_df)} materias primas que requieren atención inmediata:")
        st.dataframe(alertas_df, use_container_width=True)
    else:
        st.success("¡Todo correcto! No hay materiales por debajo del stock mínimo (30 unidades).")

# PESTAÑA 2: Registrar Movimientos
with tab2:
    st.header("Registro de Entrada / Salida de Materiales")
    
    conn = get_connection()
    productos_opciones = pd.read_sql_query("SELECT id, nombre FROM productos", conn)
    conn.close()
    
    dict_productos = {f"ID {row['id']} - {row['nombre']}": row['id'] for _, row in productos_opciones.iterrows()}
    
    with st.form("registro_movimiento_form"):
        producto_seleccionado = st.selectbox("Seleccionar Materia Prima", options=list(dict_productos.keys()))
        tipo_mov = st.radio("Tipo de Operación", options=["entrada", "salida"])
        cantidad_input = st.number_input("Cantidad", min_value=1, step=1, value=1)
        fecha_input = st.date_input("Fecha del Movimiento", value=date.today())
        
        submit_btn = st.form_submit_button("Procesar Movimiento")
        
        if submit_btn:
            prod_id = dict_productos[producto_seleccionado]
            exito, msg = registrar_movimiento(prod_id, tipo_mov, int(cantidad_input), str(fecha_input))
            if exito:
                st.success(msg)
            else:
                st.error(msg)

# PESTAÑA 3: Consultar Inventario
with tab3:
    st.header("Buscador y Reportes de Inventario")
    
    col_c, col_b = st.columns(2)
    with col_c:
        categorias_lista = ["Todas"] + list(df_inv['categoria'].unique())
        cat_sel = st.selectbox("Filtrar por Categoría", options=categorias_lista)
    with col_b:
        query = st.text_input("Buscar por nombre de material")
        
    df_filtrado = df_inv.copy()
    if cat_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['categoria'] == cat_sel]
    if query:
        df_filtrado = df_filtrado[df_filtrado['nombre'].str.contains(query, case=False)]
        
    st.dataframe(df_filtrado, use_container_width=True)
    
    # Opción de Exportar en CSV
    csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Exportar Resultado a CSV",
        data=csv_data,
        file_name="inventario_filtrado.csv",
        mime="text/csv"
    )

# PESTAÑA 4: Base de Datos Relacional
with tab4:
    st.header("Tablas de Soporte de la Base de Datos")
    conn = get_connection()
    tab_prod, tab_prove, tab_mov = st.tabs(["📦 Productos", "🏢 Proveedores", "🔄 Historial de Movimientos"])
    
    with tab_prod:
        st.dataframe(pd.read_sql_query("SELECT * FROM productos", conn), use_container_width=True)
    with tab_prove:
        st.dataframe(pd.read_sql_query("SELECT * FROM proveedores", conn), use_container_width=True)
    with tab_mov:
        st.dataframe(pd.read_sql_query("SELECT * FROM movimientos ORDER BY id DESC", conn), use_container_width=True)
    conn.close()