# Simulación Unitree Go2 — Arquitectura y Notas Técnicas

## Descripción General

Simulación completamente contenerizada del robot cuadrúpedo Unitree Go2 usando **ROS 2 Humble**, **Gazebo Fortress (Ignition 6)** y el controlador de locomoción **CHAMP**. El stack corre en Docker con acceso directo a la GPU y soporta SLAM basado en LiDAR 2D y navegación autónoma con Nav2 en un entorno de bodega industrial.

---

## Arquitectura

### Pipeline de Construcción Docker

Tres etapas de imagen secuenciales construyen el entorno completo:

| Etapa | Propósito |
|---|---|
| `base` | Instala ROS 2 Humble, integración con Gazebo Fortress (`ros-humble-ros-ign-*`, `ros-humble-ign-ros2-control`, Nav2, SLAM Toolbox). Clona `anujjain-dev/unitree-go2-ros2` (CHAMP + `go2_description` + `go2_config`), aplica parches al URDF (ver Problemas) y construye el workspace upstream en `/go2_ws`. |
| `overlay` | Copia los dos paquetes personalizados (`go2_ign_bringup`, `go2_nav`) y los compila en `/overlay_ws` con el entorno upstream ya cargado. |
| `dev` | Agrega un usuario sin privilegios de root (UID 1000) y monta ambos paquetes como volúmenes para edición en vivo desde el host sin reconstruir la imagen. |

El contenedor `dev` es el punto de entrada para el trabajo diario: se edita en el host, se ejecuta `colcon build --symlink-install` dentro del contenedor y se relanza.

### Estructura del Workspace (Dentro del Contenedor)

```
/opt/ros/humble/    — instalación de ROS 2 Humble
/go2_ws/            — upstream: CHAMP, go2_description, go2_config
/overlay_ws/        — personalizado: go2_ign_bringup, go2_nav
/entrypoint.sh      — carga los tres workspaces; configura las rutas IGN_GAZEBO_*
```

### Secuencia de Lanzamiento (`go2_sim.launch.py`)

1. **`robot_state_publisher`** — publica el URDF del Go2 (con LiDAR) en `/robot_description`
2. **Gazebo Fortress** — carga `industrial.sdf` mediante `ros_ign_gazebo`
3. **`ros_ign_gazebo create`** — instancia el robot en z = 0.35 m
4. **`ros_ign_bridge`** — comunica `/clock`, `/tf`, `/imu_raw`, `/scan_raw` entre Gazebo y ROS
5. *(retardo de 5 s)* **spawner de `joint_states_controller`** — espera a que `controller_manager` esté listo
6. **spawner de `joint_group_effort_controller`** — se activa al finalizar el paso 5 mediante `OnProcessExit`
7. **`champ_bringup`** — locomoción CHAMP: generación de marcha, estimación de estado, salida de trayectorias de articulaciones
8. **`imu_frame_relay`** — republica `/imu_raw` → `/imu/data` con `frame_id=imu_link`
9. **`scan_frame_relay`** — republica `/scan_raw` → `/scan` con `frame_id=front_laser`
10. *(retardo de 15 s)* **RViz2** (opcional)

### Componentes Principales

**`go2_ign_bringup`** — Bringup específico para Fortress. Contiene el archivo de lanzamiento principal, la configuración del bridge de tópicos `gz_bridge.yaml`, el wrapper URDF `go2_with_lidar.xacro`, el mundo SDF industrial y la configuración de RViz.

**`go2_nav`** — Utilidades de navegación y relay. Contiene `scan_frame_relay`, `imu_frame_relay`, `square_trajectory`, la configuración de SLAM Toolbox, los parámetros de Nav2, los archivos de lanzamiento y el mapa guardado de la bodega (`maps/industrial_map.*`).

**CHAMP** (`champ_bringup`) — Framework de locomoción para cuadrúpedos. Recibe `/cmd_vel`, ejecuta cinemática inversa y generación de marcha, y publica trayectorias de articulaciones en `joint_group_effort_controller/joint_trajectory`. Configurado con `close_loop_odom=false` y `orientation_from_imu=true` (ver Problemas).

---

## Decisiones Técnicas

**Interfaz de esfuerzo en lugar de posición** — El `go2_config` upstream está orientado al Go2 físico, que usa control de torque. Mantener `effort` como interfaz de comando en `JointTrajectoryController` preserva la fidelidad física y evita reajustar CHAMP para una interfaz de posición.

**Wrapper Xacro en lugar de modificar el upstream** — En vez de hacer un fork de `go2_description`, el LiDAR se agrega mediante `go2_with_lidar.xacro`, un wrapper liviano que incluye el `robot.xacro` upstream sin modificarlo. Esto mantiene el diff personalizado mínimo y facilita incorporar actualizaciones del upstream.

**Nodos de relay en lugar de transformadas estáticas** — Gazebo Fortress construye los frame IDs de los sensores como `{model}/{link}/{sensor_name}`. Publicar una transformada estática nula entre el frame con alcance de Fortress y el frame del URDF induciría a error el árbol TF (implicando un offset físico inexistente). En cambio, los nodos de relay reescriben `header.frame_id` por software, manteniendo la topología del árbol TF correcta.

**Parches al URDF en el Dockerfile** — El URDF upstream viene con nombres de plugins de Gazebo Classic. En lugar de mantener un fork separado, se aplican dos parches `sed` durante la construcción de la imagen `base` para reemplazar las referencias a plugins Classic por sus equivalentes en Fortress. Es una solución frágil, pero mantiene el clon upstream intacto.

---

## Problemas Encontrados

### 1. Nomenclatura de Plugins: Gazebo Classic vs Fortress

El URDF upstream usa nombres de plugins de Classic en todo el código (`libgazebo_ros2_control.so`, `gazebo_ros2_control`, `gazebo_ros2_control/GazeboSystem`). Fortress requiere identificadores completamente distintos (`ign_ros2_control-system`, `ign_ros2_control::IgnitionROS2ControlPlugin`, `ign_ros2_control/IgnitionSystem`). Se aplicaron parches con `sed` en el Dockerfile en tiempo de construcción. El paquete `champ_gazebo` completo (exclusivo de Classic) fue excluido del build de colcon con `--packages-ignore`.

### 2. Tipo de Sensor LiDAR y Elemento SDF Incorrecto

El sensor `gpu_lidar` de Fortress requiere un elemento hijo `<ray>` en el contexto URDF/Xacro (no `<lidar>`, como sugiere a veces la documentación de Fortress). La implementación inicial usaba `<lidar>`, lo que causaba que el sensor fallara silenciosamente. Se necesitaron múltiples commits para encontrar la estructura correcta.

### 3. frame_id con Alcance de Sensor en los Datos del LiDAR

`ros_ign_bridge` copia el frame ID interno de Ignition (`go2/base_link/front_laser_sensor`) tal cual en el encabezado del `LaserScan`. SLAM Toolbox y Nav2 buscan `front_laser` en TF, por lo que el desajuste hacía que todas las búsquedas TF fallaran silenciosamente. **Solución:** el bridge publica en `/scan_raw`; el nodo `scan_frame_relay` reescribe `header.frame_id` a `front_laser` antes de republicar en `/scan`.

### 4. Odometría de Lazo Cerrado de CHAMP Publicando Pose Estática

El modo `close_loop_odom` de CHAMP producía una salida de odometría estática (siempre en cero), lo que impedía que la transformada `odom → base_footprint` se actualizara. El robot aparecía congelado en TF aunque Gazebo lo mostraba caminando. **Solución:** se configuró `close_loop_odom=false` en los argumentos del bringup de CHAMP, volviendo a la odometría basada en cinemática. También se habilitó `orientation_from_imu=true` para fusionar la orientación del IMU en la estimación de estado.

### 5. Desajuste de frame_id del IMU con el EKF de robot_localization

El mismo problema de alcance de Fortress que afectó al LiDAR también afectó al IMU: el bridge publicaba `/imu/data` con `frame_id=go2/base_link/imu_sensor`, que no existe en el árbol TF del URDF. El EKF de `robot_localization` rechazaba silenciosamente todos los mensajes del IMU porque no podía resolver la transformada. **Solución:** el bridge fue reconfigurado para publicar los datos crudos en `/imu_raw`; el nuevo nodo `imu_frame_relay` reescribe `header.frame_id` a `imu_link` y republica en `/imu/data`.
