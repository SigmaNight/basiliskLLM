#!/usr/bin/env python3
"""Test simple pour diagnostiquer le problème de focus."""

# Test du module send_signal
print("Test des signaux...")

try:
	from basilisk.send_signal import (
		send_focus_signal,
		send_open_bskc_file_signal,
	)

	print("✓ Modules send_signal importés avec succès")

	# Test d'envoi de signal de focus
	print("Envoi du signal de focus...")
	send_focus_signal()
	print("✓ Signal de focus envoyé")

	# Test d'envoi de signal d'ouverture de fichier
	print("Envoi du signal d'ouverture de fichier...")
	send_open_bskc_file_signal("test.bskc")
	print("✓ Signal d'ouverture de fichier envoyé")

except Exception as e:
	print(f"❌ Erreur lors du test des signaux: {e}")
	import traceback

	traceback.print_exc()

# Test du singleton
print("\\nTest du singleton...")

try:
	from basilisk.singleton_instance import SingletonInstance

	print("✓ Module singleton importé avec succès")

	# Test d'acquisition du verrou
	instance = SingletonInstance("test_basilisk")
	if instance.acquire():
		print("✓ Verrou singleton acquis")

		# Test de détection d'instance existante
		instance2 = SingletonInstance("test_basilisk")
		if not instance2.acquire():
			print("✓ Deuxième instance correctement rejetée")

			existing_pid = instance2.get_existing_pid()
			if existing_pid:
				print(f"✓ PID d'instance existante détecté: {existing_pid}")
			else:
				print(
					"ℹ️ PID d'instance existante non disponible (normal sur Windows)"
				)
		else:
			print("❌ Deuxième instance incorrectement acceptée")

		instance.release()
		print("✓ Verrou singleton libéré")
	else:
		print("❌ Impossible d'acquérir le verrou singleton")

except Exception as e:
	print(f"❌ Erreur lors du test du singleton: {e}")
	import traceback

	traceback.print_exc()

print("\\nTest terminé.")
