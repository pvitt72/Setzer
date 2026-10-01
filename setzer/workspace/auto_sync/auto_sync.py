#!/usr/bin/env python3
# coding: utf-8

# Copyright (C) 2017-present Robert Griesel
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>

from gi.repository import GLib

from setzer.app.service_locator import ServiceLocator


class AutoSync(object):
    ''' scrolls the preview to the cursor position while editing. '''

    delay = 500 # ms of inactivity before syncing

    def __init__(self, workspace):
        self.workspace = workspace
        self.settings = ServiceLocator.get_settings()
        self.is_active = self.settings.get_value('preferences', 'auto_forward_sync')
        self.timeout_id = None
        self.connected_documents = set()

        self.settings.connect('settings_changed', self.on_settings_changed)
        self.workspace.connect('new_document', self.on_new_document)
        self.workspace.connect('document_removed', self.on_document_removed)

        for document in self.workspace.open_documents:
            self.connect_document(document)

    def on_settings_changed(self, settings, parameter):
        section, item, value = parameter

        if item == 'auto_forward_sync':
            self.is_active = value
            if not value:
                self.cancel_timeout()

    def on_new_document(self, workspace, document):
        self.connect_document(document)

    def on_document_removed(self, workspace, document):
        if document in self.connected_documents:
            document.disconnect('cursor_position_changed', self.on_cursor_position_changed)
            self.connected_documents.discard(document)

    def connect_document(self, document):
        if not document.is_latex_document(): return
        if document in self.connected_documents: return

        document.connect('cursor_position_changed', self.on_cursor_position_changed)
        self.connected_documents.add(document)

    def on_cursor_position_changed(self, document, parameter=None):
        if not self.is_active: return
        if document != self.workspace.active_document: return

        self.cancel_timeout()
        self.timeout_id = GLib.timeout_add(self.delay, self.on_timeout)

    def cancel_timeout(self):
        if self.timeout_id != None:
            GLib.source_remove(self.timeout_id)
            self.timeout_id = None

    def on_timeout(self):
        self.timeout_id = None
        self.sync()
        return False

    def sync(self):
        if not self.is_active: return
        if not self.workspace.show_preview: return

        active_document = self.workspace.active_document
        sync_document = self.workspace.get_root_or_active_latex_document()
        if active_document == None or sync_document == None: return
        if not sync_document.is_latex_document(): return
        if not sync_document.build_system.can_sync: return

        # a build is about to replace the .pdf and syncs on its own afterwards
        if sync_document.build_system.get_build_state() != 'idle': return

        sync_document.build_system.forward_sync_quiet(active_document)
