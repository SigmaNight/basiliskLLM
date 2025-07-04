#!/usr/bin/env python3
"""Script de test manuel pour le focus NVDA.

Ce script permet de tester manuellement le comportement du focus
avec NVDA lorsque la fenêtre est rappelée au premier plan.
"""

import sys

import wx


def create_test_frame():
	"""Crée une fenêtre de test simple."""
	app = wx.App()

	frame = wx.Frame(None, title="Test Focus NVDA - BasiliskLLM")
	frame.SetSize((400, 300))

	# Créer un panneau principal
	panel = wx.Panel(frame)
	sizer = wx.BoxSizer(wx.VERTICAL)

	# Ajouter quelques contrôles
	label = wx.StaticText(panel, label="Fenêtre de test pour NVDA")
	sizer.Add(label, 0, wx.ALL, 10)

	text_input = wx.TextCtrl(panel, value="Tapez votre message ici...")
	sizer.Add(text_input, 0, wx.ALL | wx.EXPAND, 10)

	# Bouton pour tester le focus
	def on_test_focus(event):
		"""Teste le focus forcé."""
		if sys.platform == "win32":
			try:
				import win32api
				import win32con
				import win32gui

				# Obtenir le handle de la fenêtre
				hwnd = frame.GetHandle()

				# Forcer la fenêtre au premier plan
				win32gui.SetForegroundWindow(hwnd)
				win32gui.SetActiveWindow(hwnd)

				# Envoyer Alt+Tab pour forcer la détection du changement de focus
				win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt down
				win32api.keybd_event(win32con.VK_TAB, 0, 0, 0)  # Tab down
				win32api.keybd_event(
					win32con.VK_TAB, 0, win32con.KEYEVENTF_KEYUP, 0
				)  # Tab up
				win32api.keybd_event(
					win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
				)  # Alt up

				# Focuser sur le champ de saisie
				text_input.SetFocus()

				# Envoyer Ctrl pour déclencher l'attention du lecteur d'écran
				win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # Ctrl down
				win32api.keybd_event(
					win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0
				)  # Ctrl up

				print("Focus forcé avec API Windows")

			except Exception as e:
				print(f"Erreur lors du focus forcé: {e}")
				# Fallback wxPython
				frame.SetFocus()
				frame.Raise()
				text_input.SetFocus()
		else:
			# Méthode wxPython standard
			frame.SetFocus()
			frame.Raise()
			text_input.SetFocus()

	test_button = wx.Button(panel, label="Tester le focus NVDA")
	test_button.Bind(wx.EVT_BUTTON, on_test_focus)
	sizer.Add(test_button, 0, wx.ALL, 10)

	# Bouton pour minimiser
	def on_minimize(event):
		"""Minimise la fenêtre."""
		frame.Iconize(True)

	minimize_button = wx.Button(panel, label="Minimiser")
	minimize_button.Bind(wx.EVT_BUTTON, on_minimize)
	sizer.Add(minimize_button, 0, wx.ALL, 10)

	# Instructions
	instructions = wx.StaticText(
		panel,
		label="""Instructions:
1. Minimisez la fenêtre
2. Utilisez Alt+Tab pour revenir à la fenêtre
3. Testez si NVDA annonce correctement le focus
4. Cliquez sur "Tester le focus NVDA" pour forcer le focus""",
	)
	sizer.Add(instructions, 1, wx.ALL | wx.EXPAND, 10)

	panel.SetSizer(sizer)

	# Focuser sur le champ de saisie au démarrage
	text_input.SetFocus()

	frame.Show()
	frame.Center()

	return app, frame


def main():
	"""Fonction principale."""
	print("Lancement du test de focus NVDA...")
	print("Assurez-vous que NVDA est en cours d'exécution.")

	app, frame = create_test_frame()

	try:
		app.MainLoop()
	except KeyboardInterrupt:
		print("\\nTest interrompu par l'utilisateur.")
	finally:
		app.Destroy()


if __name__ == "__main__":
	main()
