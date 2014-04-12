import sys
import types
import cherrypy
import urllib
import unittest
import re
import os

import PatchDatabaseWrapper
import PatchTimeline
import DarunGrimSessions
import DarunGrimDatabaseWrapper
import DarunGrimAnalyzers
import DownloadMSPatches
import FileStore

from mako.template import Template
from HTMLPages import *

config_file = 'DarunGrim3.cfg'

class WebServer(object):
	DebugLevel = 0
	def __init__(self):
		#Something Configurable
		self.BinariesStorageDirectory = r'C:\mat\Projects\Binaries'
		self.MicrosoftBinariesStorageDirectory = self.BinariesStorageDirectory
		self.DGFDirectory = r'C:\mat\Projects\DGFs'
		self.IDAPath = None
		self.PatchTemporaryStore = 'Patches'

		if os.path.exists( config_file ):
			fd = open( config_file )
			config_data = fd.read()
			fd.close()
			config = ConfigParser.RawConfigParser()
			config.readfp(io.BytesIO( config_data ))
					
			self.BinariesStorageDirectory = os.path.join( os.getcwd(), config.get("Directories", "BinariesStorage") )
			self.MicrosoftBinariesStorageDirectory = self.BinariesStorageDirectory
			self.DGFDirectory = os.path.join( os.getcwd(), config.get("Directories", "DGFDirectory") )
			self.IDAPath = config.get("Directories", "IDAPath")
			self.DatabaseName = config.get("Directories", "DatabaseName")
			self.PatchTemporaryStore = config.get("Directories", "PatchTemporaryStore")
		
		#Operation
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		self.PatchTimelineAnalyzer = PatchTimeline.Analyzer( database = database )
		self.DarunGrimSessionsInstance = DarunGrimSessions.Manager( self.DatabaseName, self.BinariesStorageDirectory, self.DGFDirectory, self.IDAPath )
		self.PatternAnalyzer = DarunGrimAnalyzers.PatternAnalyzer()

	def index(self):
		mytemplate = Template( IndexTemplateText )
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		patches = database.GetPatches()
		return mytemplate.render()
	index.exposed = True

	def ShowFileList(self, company_name = None, filename = None, version_string = None ):
		filenames = []
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		if company_name:
			if filename:
				if version_string:
					#Show info
					pass
				else:
					#List version strings
					file_information_list = []
					database = PatchDatabaseWrapper.Database( self.DatabaseName )
					for file_info in database.GetFileByCompanyFileName( company_name, filename ):
						fullFilename = os.path.join( self.BinariesStorageDirectory, file_info.full_path)
						archInfo = self.Is32bitExecutable( fullFilename)

						file_information_list.append( (file_info.filename, file_info.ctime, file_info.mtime, file_info.added_time, file_info.md5, file_info.sha1, file_info.id, file_info.version_string, None, archInfo ) )
						
					projects = database.GetProjects()

					mytemplate = Template( FileListTemplate, input_encoding='utf-8' , output_encoding='utf-8' )
					return mytemplate.render(  
						company_name = company_name,
						filename = filename,
						file_information_list = file_information_list,
						show_add_to_queue = True,
						projects = projects
					)
			else:
				#List filenames
				numVersions = []
				for (filename, ) in database.GetFileNames( company_name ):
					numVersion = len(database.GetFileByCompanyFileName( company_name, filename))
					filenames.append( filename )
					numVersions.append(numVersion)

				mytemplate = Template( FileListFileNamesTemplateText, input_encoding='utf-8' , output_encoding='utf-8' )
				return mytemplate.render(  
					company_name = company_name,
					filenames = filenames,
					numVersions = numVersions
				)
		else:
			#List company_names
			for (filename, ) in database.GetCompanyNames():
				filenames.append( filename )
			mytemplate = Template( FileListCompanyNamesTemplateText, input_encoding='utf-8' , output_encoding='utf-8' )
			return mytemplate.render( filenames = filenames )
	ShowFileList.exposed = True

	def Is32bitExecutable( self, filename):
		# determine the executable's base architecture, 32bit / 64bit
		# TODO - this function might be located in somewhere else
		import pefile
		pe = pefile.PE(filename)
		_32bitFlag = pefile.IMAGE_CHARACTERISTICS['IMAGE_FILE_32BIT_MACHINE']

		if ( _32bitFlag & pe.FILE_HEADER.Machine ) == _32bitFlag:
			return "32bit"
		return "64bit"

	def FileTree(self, company_name = None, filename = None, version_string = None ):
		return """<html>
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
	<script type="text/javascript" src="http://static.jstree.com/v.1.0rc2/jquery.js"></script>
	<script type="text/javascript" src="http://static.jstree.com/v.1.0rc2/jquery.cookie.js"></script>
	<script type="text/javascript" src="http://static.jstree.com/v.1.0rc2/jquery.hotkeys.js"></script>
	<script type="text/javascript" src="http://static.jstree.com/v.1.0rc2/jquery.jstree.js"></script>
</head> 

<body>
""" + MainMenu + """
<div id="demo1" class="demo"></div>
<script type="text/javascript">
$(function () {
	$("#demo1").jstree({
		"json_data" : 
			{ 
				// I chose an ajax enabled tree - again - as this is most common, and maybe a bit more complex
				// All the options are the same as jQuery's except for `data` which CAN (not should) be a function
				"ajax" : {
					// the URL to fetch the data
					"url" : "FileTreeJSON",
					// this function is executed in the instance's scope (this refers to the tree instance)
					// the parameter is the node being loaded (may be -1, 0, or undefined when loading the root nodes)
					"data" : function (n) { 
						// the result is fed to the AJAX request `data` option
						return { 
							"company_name" : n.attr ? n.attr("company_name"): "",
							"filename" : n.attr ? n.attr("filename"): "",
							"version_string" : n.attr ? n.attr("version_string"): ""
						}; 
					}
				}
			}
		,
		"plugins" : [ "themes", "json_data", "checkbox" ]
	});
});
</script>
</body>
</html>"""
	FileTree.exposed = True

	def FileTreeJSON(self, company_name = None, filename = None, version_string = None ):
		names = []
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		if company_name:
			if filename:
				if version_string:
					#Show info
					pass
				else:
					#List version strings
					print 'List version strings'
					#List filenames
					version_strings = []
					for (id, name, ) in database.GetVersionStringsWithIDs( company_name, filename ):
						tree_data = {}
						tree_data[ "data" ] = name
						tree_data[ "attr" ] = { "company_name": company_name, "filename": name }

						version_strings.append( tree_data )
					version_strings_json = json.dumps( version_strings )
					return version_strings_json
			else:
				print 'List filenames'
				#List filenames
				file_names = []
				for (name, ) in database.GetFileNames( company_name ):
					tree_data = {}
					tree_data[ "data" ] = name
					tree_data[ "attr" ] = { "company_name": company_name, "filename": name }
					tree_data[ "state" ] = "closed"

					file_names.append( tree_data )
				file_names_json = json.dumps( file_names )
				return file_names_json
		else:
			company_names = []
			for (name, ) in database.GetCompanyNames():
				tree_data = {}
				tree_data[ "data" ] = name
				tree_data[ "attr" ] = { "company_name": name, "rel": "drive" }
				tree_data[ "state" ] = "closed"

				company_names.append( tree_data )
			company_names_json = json.dumps( company_names )
			return company_names_json
	FileTreeJSON.exposed = True

	def ShowFileImport( self, folder = None, move_file = None, overwrite_mode = None ):
		mytemplate = Template( FileImportTemplateText )

		if folder:
			file_store = FileStore.FileProcessor( self.DatabaseName )
			copy_file = True
			if move_file == 'yes':
				copy_file = False

			overwrite_mode_val = False
			if overwrite_mode and overwrite_mode == 'yes':
				overwrite_mode_val = True

			file_store.IndexFilesInFolder( folder , target_dirname = self.BinariesStorageDirectory, copy_file = copy_file, overwrite_mode = overwrite_mode_val )
		return mytemplate.render( folder = folder )
	ShowFileImport.exposed = True

	def ShowFileSearch( self, type = None, search_str = None,sub_type = None, sub_search_str = None, date_type = None, datepicker_from = None, datepicker_to = None ):
		if type and search_str:
			database = PatchDatabaseWrapper.Database( self.DatabaseName )

			file_infos = []
			if type == 'Filename':
				file_infos = database.GetFileByFileNameWildMatch( search_str, sub_type , sub_search_str.lower(), date_type, datepicker_from, datepicker_to )
			elif type == 'MD5':
				file_infos = database.GetFileByMD5( search_str.lower(), sub_type , sub_search_str.lower(), date_type, datepicker_from, datepicker_to )
			elif type == 'SHA1':
				file_infos = database.GetFileBySHA1( search_str.lower(), sub_type , sub_search_str.lower(), date_type, datepicker_from, datepicker_to )
			elif type == 'File Path':
				file_infos = database.GetFileBySrcFullPathWildMatch( search_str.lower(), sub_type , sub_search_str.lower(), date_type, datepicker_from, datepicker_to )

			file_information_list = []
			for file_info in file_infos:
				file_information_list.append( (file_info.filename, file_info.ctime, file_info.mtime, file_info.added_time, file_info.md5, file_info.sha1, file_info.id, file_info.version_string, None ) )

			projects = database.GetProjects()
			mytemplate = Template( FileListTemplate, input_encoding='utf-8' , output_encoding='utf-8' )
			return mytemplate.render(  
				company_name = "",
				filename = "",
				file_information_list = file_information_list,
				show_add_to_queue = True,
				projects = projects
			)
		else:
			mytemplate = Template( """<%def name="layoutdata()">
				<form name="input" action="ShowFileSearch">
					<table>
					<tr>
						<td>
						<select name="type">
							<option value="Filename">Filename</option>
							<option value="MD5">MD5</option>
							<option value="SHA1">SHA1</option>
							<option value="File Path">File Path</option>
						</select>
						</td>

						<td colspan=2>
							<input type="text" size="50" name="search_str" value=""/>
						</td>
					</tr>

					<tr>
						<td>
						<select name="sub_type">
							<option value="CompanyName">Company Name</option>
						</select>
						</td>

						<td colspan=2>
							<input type="text" size="50" name="sub_search_str" value=""/>
						</td>
					</tr>

					<tr>
						<td>
							<select name="date_type">
								<option value="CreatedDate">Created Date</option>
								<option value="ModifiedDate">Modified Date</option>
								<option value="AddedDate">Added Date</option>
							</select>
						</td>

						<td>
							<input id="datepicker_from" type="text" name="datepicker_from" value="">
						</td>
						
						<td>
							<input id="datepicker_to" type="text" name="datepicker_to" value="">
						</td>
					</tr>
					<table>
					<p><input type="submit" value="Search"/>
				</form>		
			</%def>
			""" + BodyHTML )

			return mytemplate.render()
	ShowFileSearch.exposed = True

	def ShowMSPatchList( self, operation = '' ):
		if operation == 'update':
			patch_downloader = DownloadMSPatches.PatchDownloader( self.PatchTemporaryStore, self.DatabaseName )
			patch_downloader.DownloadCurrentYearPatches()

		mytemplate = Template( PatchesTemplateText )
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		patches = database.GetPatches()
		return mytemplate.render( patches=patches )
	ShowMSPatchList.exposed = True

	def PatchInfo( self, id ):
		mytemplate = Template( PatchInfoTemplateText )
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		downloads = database.GetDownloadByPatchID( id )
		return mytemplate.render( id=id, downloads=downloads )
	PatchInfo.exposed = True

	def DownloadInfo(self, patch_id, id, operation = '' ):
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		if operation == 'extract':
			patch_temporary_folder = tempfile.mkdtemp()
			patch_temporary_folder2 = tempfile.mkdtemp()
			file_store = FileStore.MSFileProcessor( patch_temporary_folder, self.MicrosoftBinariesStorageDirectory, database = database )
			patch_downloader = DownloadMSPatches.PatchDownloader( patch_temporary_folder2, self.DatabaseName )
			for download in database.GetDownloadByID( id ):
				print 'Extracting', download.filename, download.url
				if not os.path.isfile( download.filename ):
					files = patch_downloader.DownloadFileByLink( download.url )
				file_store.ExtractDownload( download, files[0] )
			try:
				os.removedirs( patch_temporary_folder2 )
			except:
				pass

			try:
				os.removedirs( patch_temporary_folder )
			except:
				pass

		files = database.GetFileByDownloadID( id )

		mytemplate = Template( DownloadInfoTemplateText )
		return mytemplate.render( 
				patch_id = patch_id, 
				patch_name = database.GetPatchNameByID( patch_id ), 
				id = id,
				files = files 
			)
	DownloadInfo.exposed = True

	def FileInfo( self, patch_id, download_id, id ):
		#PatchTimeline
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		files = database.GetFileByID( id )
		print 'files', files
		[ file_index_entry ] = files
		filename = file_index_entry.filename
		target_patch_name = file_index_entry.downloads.patches.name

		source_id = 0
		source_patch_name = 'Not Found'
		source_filename = 'Not Found'
		target_filename = filename
		target_id = 0
		print 'FileInfo: filename=', filename
		for ( target_patch_name, target_file_entry, source_patch_name, source_file_entry ) in self.PatchTimelineAnalyzer.GetPatchPairsForAnalysis( filename = filename, id = id, patch_name = target_patch_name ):
			print '='*80
			print target_patch_name,source_patch_name

			source_filename = source_file_entry['full_path']
			source_id = source_file_entry['id']

			target_filename = target_file_entry['full_path']
			target_id = target_file_entry['id']

		mytemplate = Template( FileInfoTemplateText )
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		return mytemplate.render(
			patch_id = patch_id,
			patch_name = database.GetPatchNameByID( patch_id ), 
			download_id = download_id,
			download_label = database.GetDownloadLabelByID( download_id),
			id = id,
			file_index_entry=file_index_entry, 
			source_patch_name = source_patch_name, 
			source_filename = source_filename,
			source_id = source_id,
			target_patch_name = target_patch_name, 
			target_filename = target_filename,
			target_id = target_id
		)
	FileInfo.exposed = True

	## Project Related ############################################################
	def ShowProjects( self ):
		#Show Add form
		mytemplate = Template( """<%def name="layoutdata()">
			<table id="mainTable" class="SortedTable">
				<thead>
				<tr>
					<th>Name</th>
					<th>Description</th>
					<th>Edit</th>
					<th>Remove</th>
				</tr>
				</thead>
				
				<tbody>
				% for project in projects:
					<tr>
						<td><a href="ShowProject?project_id=${project.id}">${project.name}</a></td>
						<td>${project.description}&nbsp;</td>
						<td><a href="ShowEditProject?project_id=${project.id}">Edit</a></td>
						<td><a href="RemoveProject?project_id=${project.id}">Remove</a></td>
					</tr>
				% endfor
				</tbody>
			</table>

			<hr>
			<a href="ShowAddProjectPage">New Project</a>
		</%def>
		""" + BodyHTML )

		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		items = []
		try:
			projects = database.GetProjects()
		except:
			pass
		return mytemplate.render( projects = projects )
	ShowProjects.exposed = True

	def ShowEditProject( self, project_id ):
		#Show Add form
		mytemplate = Template( """<%def name="layoutdata()">
			<form name="input" action="UpdateProject">
				<table>
				<tr>
					<td>Name</td>
					<td><input type="text" size="50" name="name" value="${name}" /></td>
				</tr>
				<tr>
					<td>Description</td>
					<td><textarea cols="80" rows="10" name="description"/>${description}</textarea></td>
				</tr>
				<table>
				<input type="hidden" name="project_id" value=${project_id} />
				<p><input type="submit" value="Update"/>
			</form>
		</%def>
		""" + BodyHTML )
		
		#pass project_id name, description info
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		project = database.GetProject( project_id )	
		return mytemplate.render( project_id = project_id, name = project.name, description = project.description )		

	ShowEditProject.exposed = True
	
	def UpdateProject( self, project_id, name, description ):
		#Edit project by project_id
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		database.UpdateProject( project_id, name, description )
		return self.ShowProjects()
	UpdateProject.exposed = True

	def RemoveProject( self, project_id ):
		#Remove project by project_id
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		database.RemoveProject( project_id )
		return self.ShowProjects()
	RemoveProject.exposed = True
	
	def RemoveFromProject( self, project_member_id, project_id ):
		#Remove project_member_id from project		
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		
		#Add to project
		if type(project_member_id)!=type(list()):
			project_member_id = [project_member_id]
		
		for one_project_member_id in project_member_id:
			database.RemoveProjectMember( one_project_member_id )
		return self.ShowProject( project_id )
	RemoveFromProject.exposed = True

	def ShowAddProjectPage( self ):
		#Show Add form
		mytemplate = Template( """<%def name="layoutdata()">
			<form name="input" action="AddProject">
				<table>
				<tr>
					<td>Name</td>
					<td><input type="text" size="50" name="name" value="" /> </td>
				</tr>
				<tr>
					<td>Description</td>
					<td><textarea cols="80" rows="10" name="description"/></textarea></td>
				</tr>
				<table>
				<p><input type="submit" value="Add"/>
			</form>
		</%def>
		""" + BodyHTML )

		return mytemplate.render()
	ShowAddProjectPage.exposed = True

	def AddProjectImpl( self, name, description = '' ):
			database = PatchDatabaseWrapper.Database( self.DatabaseName )
			project = database.AddProject( name, description )
			database.Commit()
			return project

	def AddProject( self, name, description = '' ):
		if name:
			self.AddProjectImpl( name, description )
			return self.ShowProjects()
		else:
			#TODO: Show error message
			return self.ShowAddProjectPage()		
	AddProject.exposed = True

	def ShowProject( self, project_id = None ):
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		project_members = database.GetProjectMembers( project_id )

		file_information_list = []
		for project_member in project_members:
			if project_member.fileindexes:
				file_info  = project_member.fileindexes
				file_information_list.append( (file_info.filename, file_info.ctime, file_info.mtime, file_info.added_time, file_info.md5, file_info.sha1, file_info.id, file_info.version_string, project_member.id ) )

		project_results = database.GetProjectResults( project_id = project_id )
		print 'project_results=',project_results
		
		project_result_list = []
		for project_result in project_results:
			print '\t', project_result.project_id, project_result.projects.name, project_result.source_file_id, project_result.target_file_id
			
			source_file = database.GetFileByID( project_result.source_file_id )[0]
			target_file = database.GetFileByID( project_result.target_file_id )[0]
			project_result_list.append(
				(
					project_result.source_file_id,
					project_result.target_file_id,
					source_file.filename,
					source_file.version_string,
					target_file.filename,
					target_file.version_string
				)
			)
		
		mytemplate = Template( ProjectContentTemplate, input_encoding='utf-8' , output_encoding='utf-8' )
		return mytemplate.render(  
			company_name = "",
			filename = "",
			file_information_list = file_information_list,
			project_id = project_id,
			show_add_to_queue = False,
			project_result_list = project_result_list
		)
	ShowProject.exposed = True

	def AddToProject( self, id = None, project_id = None, new_project_name = None, allbox = None ):
		#Display project choose list
		items = []
		
		if new_project_name and new_project_name != "":
			#Create new project
			project = self.AddProjectImpl( new_project_name, "" )
			#assign project_id = project.id
			project_id = project.id

		if not project_id:
			return ""

		if not id:
			return self.ShowProject( project_id )

		#Add to project
		if type(id)!=type(list()):
			id = [id]
		
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		if not project_id:
			projects = database.GetProjects()
			mytemplate = Template( ProjectSelectionTemplate + BodyHTML )
			return mytemplate.render( ids = id, projects = projects )
		else:
			for one_id in id:
				database.AddToProject( project_id, one_id )
				database.Commit()
			return self.ShowProject( project_id )

	AddToProject.exposed = True
	##############################################################################
	
	def GenerateDGFName( self, source_id, target_id ):
		return os.path.join( self.DGFDirectory, str( source_id ) + '_' + str( target_id ) + '.dgf')

	def ProcessProjectContent( self, source_id = None, target_id = None, operation = None, project_member_id = None,  patch_id = 0, download_id = 0, file_id = 0, show_detail = 0, project_id = None, allbox = None ):
		print 'operation=',operation
		print 'project_member_id=',project_member_id

		if operation == "Start Diffing":
			return self.StartDiff( source_id, target_id, patch_id, download_id = download_id, file_id = file_id, show_detail = show_detail, project_id = project_id )
		elif operation == "Remove From Project":
			return self.RemoveFromProject( project_member_id, project_id )
		
		#TODO: Put a better error page
		return "Error"

	ProcessProjectContent.exposed = True

	def StartDiff( self, source_id, target_id, patch_id = 0, download_id = 0, file_id = 0, show_detail = 0, reset = 'no', project_id = None ):
		databasename = self.GenerateDGFName( source_id, target_id )

		reset_database = False
		if reset == 'yes':
			reset_database = True

		self.DarunGrimSessionsInstance.InitFileDiffByID( source_id, target_id, databasename, reset_database )

		#Add or Update Project
		if project_id:
			patch_database = PatchDatabaseWrapper.Database( self.DatabaseName )
			patch_database.AddProjectResult( project_id, source_id, target_id, databasename)

		databasename = self.GenerateDGFName( source_id, target_id )
		database = DarunGrimDatabaseWrapper.Database( databasename )

		#Check if dgf if correct? check size entries in GetFunctionMatchInfoCount?.
		if database.GetFunctionMatchInfoCount() == 0:
			#Remove DatabaseName
			del database
			self.DarunGrimSessionsInstance.RemoveDiffer ( source_id, target_id )
			try:
				os.remove( self.DarunGrimSessionsInstance.DatabaseName )
			except:
				print 'Error removing database file', self.DarunGrimSessionsInstance.DatabaseName
			#Show error page?

			if self.DebugLevel > 3:
				print 'LogFilename', self.DarunGrimSessionsInstance.LogFilename
				print 'LogFilenameForSource', self.DarunGrimSessionsInstance.LogFilenameForSource
				print 'LogFilenameForTarget', self.DarunGrimSessionsInstance.LogFilenameForTarget

			log = ''
			log_for_source = ''
			log_for_target = ''
			try:
				fd = open( self.DarunGrimSessionsInstance.LogFilename )
				log = fd.read()
				fd.close()
			except:
				pass

			try:
				fd = open( self.DarunGrimSessionsInstance.LogFilenameForSource )
				log_for_source = fd.read()
				fd.close()
			except:
				pass

			try:
				fd = open( self.DarunGrimSessionsInstance.LogFilenameForTarget )
				log_for_target = fd.read()
				fd.close()
			except:
				pass

			mytemplate = Template( """<%def name="layoutdata()">
					<title>Something is wrong with IDA execution.</title>
					<table>
					<tr>
						<td><b>Log for Source(${source_filename})</b></td>
					</tr>
					<tr>
						<td><pre>${log_for_source}</pre></td>
					</tr>

					<tr>
						<td><b>Log for Target(${target_filename})</b></td>
					</tr>
					<tr>
						<td><pre>${log_for_target}</pre></td>
					</tr>

					<tr>
						<td><b>Darungrim Plugin Log</b></td>
					</tr>
					<tr>
						<td><pre>${log}</pre></td>
					</tr>
					<table>
			</%def>
			""" + BodyHTML )

			return mytemplate.render( log = log,
				log_for_source = log_for_source,
				log_for_target = log_for_target,
				source_filename = self.DarunGrimSessionsInstance.SourceFileName,
				target_filename = self.DarunGrimSessionsInstance.TargetFileName
			)
		else:
			return self.GetFunctionMatchInfo( 
				patch_id, 
				download_id, 
				file_id, 
				source_id=source_id,
				target_id = target_id,
				show_detail  = show_detail,
				project_id = project_id
				)
	StartDiff.exposed = True

	def GetFunctionMatchInfo( self, patch_id, download_id, file_id, source_id, target_id, show_detail = 0, project_id = None ):
		databasename = self.GenerateDGFName( source_id, target_id )
		database = DarunGrimDatabaseWrapper.Database( databasename )

		function_match_infos = []
		
		for function_match_info in database.GetFunctionMatchInfo():
			if function_match_info.non_match_count_for_the_source > 0 or \
				function_match_info.non_match_count_for_the_target > 0 or \
				function_match_info.match_count_with_modificationfor_the_source > 0:
				function_match_infos.append( function_match_info )

		patch_database = PatchDatabaseWrapper.Database( self.DatabaseName )
		source_file = patch_database.GetFileByID( source_id )[0]
		target_file = patch_database.GetFileByID( target_id )[0]

		mytemplate = Template( FunctionmatchInfosTemplateText )
		return mytemplate.render(
				source_file_name = source_file.filename,
				source_file_version_string = source_file.version_string,
				target_file_name = target_file.filename,
				target_file_version_string = target_file.version_string,		
				patch_id = patch_id, 
				patch_name = patch_database.GetPatchNameByID( patch_id ), 
				download_id = download_id, 
				download_label = patch_database.GetDownloadLabelByID( download_id),
				file_id = file_id, 
				file_name = patch_database.GetFileNameByID( file_id ),  
				source_id=source_id, 
				target_id = target_id, 
				function_match_infos = function_match_infos,
				show_detail = 0,
				project_id = project_id
			)

	def ShowFunctionMatchInfo( self, patch_id, download_id, file_id, source_id, target_id ):
		return self.GetFunctionMatchInfo( patch_id, download_id, file_id, source_id, target_id )
	ShowFunctionMatchInfo.exposed = True

	def ShowBasicBlockMatchInfo( self, patch_id, download_id, file_id, source_id, target_id, source_address, target_address ):
		return self.GetDisasmComparisonTextByFunctionAddress( patch_id, download_id, file_id, source_id, target_id, source_address, target_address )
	ShowBasicBlockMatchInfo.exposed = True

	def GetDisasmComparisonTextByFunctionAddress( self, 
			patch_id, download_id, file_id, 
			source_id, target_id, source_address, target_address, 
			source_function_name = None, target_function_name = None ):

		patch_database = PatchDatabaseWrapper.Database( self.DatabaseName )
		source_file = patch_database.GetFileByID( source_id )[0]
		target_file = patch_database.GetFileByID( target_id )[0]
	
		databasename = self.GenerateDGFName( source_id, target_id )
		darungrim_database = DarunGrimDatabaseWrapper.Database( databasename )

		source_address = int(source_address)
		target_address = int(target_address)

		self.DarunGrimSessionsInstance.ShowAddresses( source_id, target_id, source_address, target_address )

		if not source_function_name:
			source_function_name = darungrim_database.GetBlockName( 1, source_address )

		if not target_function_name:
			target_function_name = darungrim_database.GetBlockName( 2, target_address )
		
		comparison_table = darungrim_database.GetDisasmComparisonTextByFunctionAddress( source_address, target_address )
		text_comparison_table = []

		left_line_security_implications_score_total = 0
		right_line_security_implications_score_total = 0
		for ( left_address, left_lines, right_address, right_lines, match_rate ) in comparison_table:
			left_line_security_implications_score = 0
			right_line_security_implications_score = 0
			if (right_address == 0 and left_address !=0) or match_rate < 100 :
				( left_line_security_implications_score, left_line_text ) = self.PatternAnalyzer.GetDisasmLinesWithSecurityImplications( left_lines, right_address == 0 )
			else:
				left_line_text = "<p>".join( left_lines )

			if (left_address == 0 and right_address !=0) or match_rate < 100 :
				( right_line_security_implications_score, right_line_text ) = self.PatternAnalyzer.GetDisasmLinesWithSecurityImplications( right_lines, left_address == 0 )
			else:
				right_line_text = "<p>".join( right_lines )

			left_line_security_implications_score_total += left_line_security_implications_score
			right_line_security_implications_score_total += right_line_security_implications_score
			text_comparison_table.append(( left_address, left_line_text, right_address, right_line_text, match_rate ) )
		
		( source_address_infos, target_address_infos ) = darungrim_database.GetBlockAddressMatchTableByFunctionAddress( source_address, target_address )
		self.DarunGrimSessionsInstance.ColorAddresses( source_id, target_id, source_address_infos, target_address_infos )

		mytemplate = Template( ComparisonTableTemplateText )
		return mytemplate.render(
				source_file_name = source_file.filename,
				source_file_version_string = source_file.version_string,
				target_file_name = target_file.filename,
				target_file_version_string = target_file.version_string,
				source_function_name = source_function_name, 
				target_function_name = target_function_name,
				comparison_table = text_comparison_table, 
				source_id = source_id, 
				target_id = target_id, 
				source_address = source_address,
				target_address = target_address,
				patch_id = patch_id, 
				patch_name = patch_database.GetPatchNameByID( patch_id ), 
				download_id = download_id, 
				download_label = patch_database.GetDownloadLabelByID( download_id),
				file_id = file_id,
				file_name = patch_database.GetFileNameByID( file_id ),  
			)

	def SyncIDA( self, source_id, target_id ):
		self.DarunGrimSessionsInstance.SyncIDA( source_id, target_id )
		return SyncIDAHTML % CloseButtonHTML
	SyncIDA.exposed = True
	
	def OpenInIDA( self, id ):
		database = PatchDatabaseWrapper.Database( self.DatabaseName )
		file_path = ''
		for file in database.GetFileByID( id ):
			file_path = file.full_path
			
		file_path = os.path.join( self.BinariesStorageDirectory, file_path )
		target_file_path = file_path
		
		idb_file_path = file_path[:-4] + '.idb'
		if os.path.exists( idb_file_path ):
			target_file_path = idb_file_path
		import subprocess
		subprocess.Popen( [ self.IDAPath, target_file_path ] )

		return OpenInIDAHTML % ( self.IDAPath, target_file_path, CloseButtonHTML )
	OpenInIDA.exposed = True

if __name__ == '__main__':
	import ConfigParser
	import io
	import sys

	if len( sys.argv ) > 1:
		config_file = sys.argv[1]

	print 'Configuration file is ' + config_file
	fd = open( config_file )
	config_data = fd.read()
	fd.close()

	config = ConfigParser.RawConfigParser()
	config.readfp(io.BytesIO( config_data ))
					
	port = int( config.get("Global", "Port") )

	cherrypy.config.update({'server.socket_host': '127.0.0.1',
                        'server.socket_port': port,
    			'response.timeout': 1000000
                       })
	config = {
		'/data': {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': os.path.join(os.getcwd(), 'data'),
			'tools.staticdir.content_types': {
				'js': 'application/javascript',
				'atom': 'application/atom+xml'
			}
		}
	}
	
	cherrypy.tree.mount( WebServer(), config=config )
	cherrypy.engine.start()
	cherrypy.engine.block()

