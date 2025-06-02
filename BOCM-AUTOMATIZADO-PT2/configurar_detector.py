"""
Script de configuración automática para el Detector Inteligente BOCM
Configura el sistema para usar solo la detección inteligente de cambios
"""

import os
import json
import shutil
from datetime import datetime

def configurar_detector_inteligente():
    """Configura el sistema para usar el detector inteligente"""
    

    #Este archivo, llamado configurar_detector.py, es un script en Python diseñado para configurar
    #un sistema llamado "Detector Inteligente BOCM". Su propósito principal es preparar el entorno 
    #necesario para que el sistema funcione correctamente, asegurándose de que los archivos, directorios 
    #y configuraciones requeridas estén en su lugar. 

    print("🔧 CONFIGURANDO DETECTOR INTELIGENTE BOCM")
    print("=" * 50)
    
    # 1. Verificar archivos necesarios
    archivos_necesarios = [
        'detector_patrones_cambio.py',
        'main_inteligente.py', 
        'tester_detector.py',
        'bocm_scraper.py',
        'config.py',
        'utils.py'
    ]
    
    print("\n📋 Verificando archivos necesarios...")
    for archivo in archivos_necesarios:
        if os.path.exists(archivo):
            print(f"   ✅ {archivo}")
        else:
            print(f"   ❌ {archivo} - FALTANTE")
            return False
    
    # 2. Crear backup del main original
    if os.path.exists('main.py'):
        backup_name = f'main_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.py'
        shutil.copy('main.py', backup_name)
        print(f"\n💾 Backup creado: {backup_name}")
    
    # 3. Crear base de conocimiento vacía si no existe
    if not os.path.exists('codigos_convenios.json'):
        with open('codigos_convenios.json', 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        print("📄 Archivo de base de conocimiento creado")
    
    # 4. Crear directorios necesarios
    directorios = ['convenios_bocm', 'convenios_referencia']
    for directorio in directorios:
        if not os.path.exists(directorio):
            os.makedirs(directorio)
            print(f"📁 Directorio creado: {directorio}")
    
    # 5. Configurar permisos de archivos principales
    archivos_ejecutables = ['main_inteligente.py', 'tester_detector.py']
    for archivo in archivos_ejecutables:
        if os.path.exists(archivo):
            # En Windows no necesitamos chmod, pero lo documentamos
            print(f"🔧 Configurado: {archivo}")
    
    print("\n✅ CONFIGURACIÓN COMPLETADA")
    print("\n🚀 PRÓXIMOS PASOS:")
    print("   1. Ejecuta: python tester_detector.py")
    print("   2. Prueba con una fecha específica")
    print("   3. Una vez confirmado, usa: python main_inteligente.py")
    
    return True

def mostrar_instrucciones():
    """Muestra las instrucciones de uso"""
    
    print("\n" + "="*60)
    print("📖 INSTRUCCIONES DE USO DEL DETECTOR INTELIGENTE")
    print("="*60)
    
    print("\n🧪 MODO PRUEBAS (Recomendado para empezar):")
    print("   python tester_detector.py")
    print("   - Prueba fechas específicas")
    print("   - Ve exactamente qué detecta")
    print("   - No modifica nada")
    
    print("\n🤖 MODO PRODUCCIÓN:")
    print("   python main_inteligente.py")
    print("   - Procesa el día actual")
    print("   - O fechas específicas")
    print("   - Lista para integrar con BD")
    
    print("\n🔍 EJEMPLO DE PRUEBA:")
    print("   1. Ejecuta: python tester_detector.py")
    print("   2. Selecciona opción 1 (fecha específica)")
    print("   3. Ingresa: 20250524")
    print("   4. Observa los resultados")
    
    print("\n⚠️  IMPORTANTE:")
    print("   - El sistema SOLO procesa convenios con cambios de código")
    print("   - Si un día no detecta nada, es NORMAL")
    print("   - La mayoría de días NO tienen cambios")
    
    print("\n🔧 PERSONALIZACIÓN:")
    print("   - Edita detector_patrones_cambio.py para ajustar patrones")
    print("   - Prueba siempre con tester_detector.py después de cambios")

def main():
    """Función principal del configurador"""
    
    print("🚀 CONFIGURADOR DEL DETECTOR INTELIGENTE BOCM")
    print("=" * 55)
    print("Este script configura el sistema para detectar SOLO convenios")
    print("con cambios reales en códigos, evitando descargas innecesarias.\n")
    
    # Confirmar configuración
    respuesta = input("¿Deseas configurar el detector inteligente? (s/n): ").lower().strip()
    
    if respuesta in ['s', 'si', 'sí', 'y', 'yes']:
        exito = configurar_detector_inteligente()
        
        if exito:
            mostrar_instrucciones()
            
            # Ofrecer prueba inmediata
            print("\n" + "="*60)
            prueba = input("¿Deseas hacer una prueba ahora? (s/n): ").lower().strip()
            
            if prueba in ['s', 'si', 'sí', 'y', 'yes']:
                print("\n🧪 Iniciando modo de pruebas...")
                try:
                    os.system('python tester_detector.py')
                except Exception as e:
                    print(f"❌ Error ejecutando pruebas: {e}")
                    print("   Ejecuta manualmente: python tester_detector.py")
    else:
        print("❌ Configuración cancelada")
        print("   Para configurar más tarde, ejecuta este script nuevamente")

if __name__ == "__main__":
    main()
