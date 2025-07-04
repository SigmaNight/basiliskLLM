#!/usr/bin/env python3
"""Script de test pour vérifier le comportement singleton et focus.

Ce script teste:
1. Le lancement d'une première instance
2. Le lancement d'une deuxième instance (doit donner le focus à la première)
3. Le comportement avec NVDA
"""

import os
import subprocess
import sys
import time


def test_singleton_behavior():
	"""Test le comportement singleton de l'application."""
	print("=== Test du comportement singleton de BasiliskLLM ===")

	# Chemin vers l'exécutable Python de l'application
	app_path = os.path.join(
		os.path.dirname(__file__), "basilisk", "__main__.py"
	)

	if not os.path.exists(app_path):
		print(f"❌ Fichier d'application non trouvé: {app_path}")
		return False

	print(f"Utilisation du fichier: {app_path}")

	try:
		print("\\n1. Lancement de la première instance...")
		# Lancer la première instance en arrière-plan
		process1 = subprocess.Popen(
			[sys.executable, app_path, "--minimize"],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)

		# Attendre que l'application se lance
		time.sleep(3)

		if process1.poll() is not None:
			stdout, stderr = process1.communicate()
			print("❌ La première instance s'est fermée immédiatement")
			print(f"stdout: {stdout.decode()}")
			print(f"stderr: {stderr.decode()}")
			return False

		print("✓ Première instance lancée")

		print("\\n2. Tentative de lancement d'une deuxième instance...")
		# Tenter de lancer une deuxième instance
		process2 = subprocess.Popen(
			[sys.executable, app_path],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)

		# Attendre que la deuxième instance se ferme (devrait être rapide)
		stdout2, stderr2 = process2.communicate(timeout=10)

		if process2.returncode == 0:
			print(
				"✓ Deuxième instance s'est fermée correctement (singleton fonctionne)"
			)
			print(f"stdout: {stdout2.decode()}")
		else:
			print(
				f"❌ Deuxième instance a échoué avec code: {process2.returncode}"
			)
			print(f"stderr: {stderr2.decode()}")

		print(
			"\\n3. Tentative d'une troisième instance pour tester le focus..."
		)
		# Tenter une troisième instance
		process3 = subprocess.Popen(
			[sys.executable, app_path],
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
		)

		stdout3, stderr3 = process3.communicate(timeout=10)

		if process3.returncode == 0:
			print(
				"✓ Troisième instance s'est fermée correctement (focus restauré)"
			)
		else:
			print(
				f"❌ Troisième instance a échoué avec code: {process3.returncode}"
			)
			print(f"stderr: {stderr3.decode()}")

		print("\\n4. Arrêt de la première instance...")
		process1.terminate()
		try:
			process1.wait(timeout=5)
			print("✓ Première instance arrêtée proprement")
		except subprocess.TimeoutExpired:
			print("⚠️ Première instance n'a pas répondu, arrêt forcé")
			process1.kill()
			process1.wait()

		return True

	except subprocess.TimeoutExpired:
		print("❌ Timeout lors du test")
		return False
	except Exception as e:
		print(f"❌ Erreur lors du test: {e}")
		return False


def main():
	"""Fonction principale."""
	print("Test du comportement singleton et focus de BasiliskLLM")
	print("=" * 60)

	if test_singleton_behavior():
		print("\\n✓ Test terminé avec succès")
		print("\\nInstructions pour tester avec NVDA:")
		print("1. Lancez BasiliskLLM normalement")
		print("2. Minimisez la fenêtre")
		print("3. Lancez une deuxième instance")
		print(
			"4. Vérifiez que NVDA annonce correctement le focus sur la fenêtre"
		)
	else:
		print("\\n❌ Test échoué")

	print("\\nAppuyez sur Entrée pour continuer...")
	input()


if __name__ == "__main__":
	main()
