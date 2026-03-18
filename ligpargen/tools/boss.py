"""

Module with BOSS software related functions to generate inputs, execute and parse outputs.

Author: Israel Cabeza de Vaca Lopez
Email:  israel.cabezadevaca@icm.uu.se

"""



import os
import shutil
import subprocess

from ..tools import utilities

import logging
logger = logging.getLogger(__name__)


def generatePARFile(cgen, charge, estimation, generateCharges, filename='parFile.par'):
   """
   Generate a BOSS PAR file (parameters files)

   Parameters
   ----------
   cgen : str, ('CM1A', CM1A-LBCC')
       Charge method
   charge : int
       Formal charge of the molecule
   estimation : str
       BOSS parameter
   generateCharges : bool
       If True, charges are computed by BOSS
   filename : str, optional
       Output filename, by default 'parFile.par'
   """

   line = '         0.00  0  0  0'

   if generateCharges==True:

      line = 'AM1SCM1L 1.14  0  0  0'  # default LBCC

      if cgen=='CM1A':

         if charge == 0: line = 'AM1SCM1A 1.14  0  0  0'
         else: line = 'AM1SCM1A {:4.2f}{:3d}{:3d}{:3d}'.format(1.0,charge,charge,charge)


   newParFile  = scriptPAR.replace('aaaa', line).replace('bbbbb', estimation)

   with open(filename, 'w') as f: f.write(newParFile)


def generateCMDFile(mode, outName, cmdFileName='bosscmd', MCsteps=000000, alchemicalTransformation = False):
   """
   Generate CMD BOSS file (command csh file)

   Parameters
   ----------
   mode : int
       BOSS mode (111, 711, ...)
   outName : str
       OUT BOSS file name
   cmdFileName : str, optional
       CMD BOSS file name, by default 'bosscmd'
   MCsteps : int, optional
       Monte Carlo steps, by default 000000
   alchemicalTransformation : bool, optional
       If True, alchemical transformation is considered, by default False
   """

   newScriptCMD = scriptCMD.replace('aaaa', outName).replace('bbbb', mode).replace('cccc', str(MCsteps))

   if alchemicalTransformation: newScriptCMD = scriptCMDFEP
      
   with open(cmdFileName, 'w') as f: f.write(newScriptCMD)


def generateCMDFEPFile(cmdFileName, workdir, forward= True):
   
   import numpy as np   

   
   dlambda = 0.05

   windowsformat = ['%4.3f' % i for i in np.arange(0,1.00000001,dlambda)] 

   cmdlines = '''           if ($i == aaaa) then 

               set rc0 = "bbbb"
               set rc1 = "cccc"
               set rc2 = "dddd"
               set lab = "eeee"
               set nex = "ffff"

           endif

'''

   newLines = ''

   if forward:
          
      nexData = windowsformat[3::2]

      for i,(rc1,rc0,rc2) in enumerate(zip(windowsformat[::2], windowsformat[1::2], windowsformat[2::2])):
            
         lab = str(int(float(rc0)*1000)).zfill(3)
         try: nex = str(int(float(nexData[i])*1000)).zfill(3)
         except: nex = str(int(float(rc2)*1000)).zfill(3)

         newLines += cmdlines.replace('aaaa',str(i)).replace('bbbb',rc0).replace('cccc',rc1).replace('dddd',rc2).replace('eeee',lab).replace('ffff',nex)

   else:
   
      windowsformatReversed = windowsformat[::-1]
      nexData = windowsformatReversed[3::2]

      for i,(rc1,rc0,rc2) in enumerate(zip(windowsformatReversed[::2], windowsformatReversed[1::2], windowsformatReversed[2::2])):

         lab = str(int(float(rc0)*1000)).zfill(3)
         try: nex = str(int(float(nexData[i])*1000)).zfill(3)
         except: nex = str(int(float(rc2)*1000)).zfill(3)

         newLines += cmdlines.replace('aaaa',str(i)).replace('bbbb',rc0).replace('cccc',rc1).replace('dddd',rc2).replace('eeee',lab).replace('ffff',nex)


   newScriptCMD = scriptCMDFEP.replace('aaaa',str(len(windowsformat[2::2]))).replace('bbbb',newLines)

   with open(os.path.join(workdir, cmdFileName),'w') as f: f.write(newScriptCMD)

def _getBossCommand(workdir, checkrun):
   """
   Determine how to invoke BOSS. Returns the shell command string to run run_boss.csh.

   $BOSSdir controls the mode:
     - Directory containing the BOSS binary  → native execution via csh
     - Path to a .sif / .simg file           → Singularity container
     - Anything else                          → Docker image name

   For container modes, $BOSS_EXEC_DIR sets the BOSS installation path *inside*
   the container (default: /boss).
   """

   bossdir = os.environ.get('BOSSdir', '')

   if not bossdir:
      logger.error(
         'BOSS is not available. Set $BOSSdir to:\n'
         '  - your BOSS installation directory (native), or\n'
         '  - a Singularity .sif image path, or\n'
         '  - a Docker image name'
      )
      exit()

   abs_workdir = os.path.abspath(workdir)
   internal_bossdir = os.environ.get('BOSS_EXEC_DIR', '/boss')

   # Singularity container (.sif / .simg) — check extension first so that
   # sandbox-format images (which are directories) are handled correctly
   if bossdir.endswith('.sif') or bossdir.endswith('.simg'):

      if not os.path.exists(bossdir):
         logger.error(f'Singularity image not found at {bossdir}.')
         exit()

      runner = shutil.which('apptainer') or shutil.which('singularity')

      if runner is None:
         logger.error('$BOSSdir points to a .sif but neither apptainer nor singularity found in PATH.')
         exit()

      logger.info(f'Running BOSS via Singularity: {bossdir}')
      return (f'{runner} exec --env BOSSdir={internal_bossdir}'
              f' -B {abs_workdir}:/workspace --pwd /workspace {bossdir} csh run_boss.csh')

   # Native: directory containing the BOSS binary
   if os.path.isdir(bossdir):

      bossExe = os.path.join(bossdir, 'BOSS')

      if not os.path.isfile(bossExe):
         logger.error(f'BOSS executable not found at {bossExe}. Check your $BOSSdir installation.')
         exit()

      prefix = 'source ~/.bashrc; ' if not checkrun else ''

      return prefix + 'csh run_boss.csh'

   # Docker image
   if shutil.which('docker') is None:
      logger.error('$BOSSdir looks like a Docker image but docker is not found in PATH.')
      exit()

   logger.info(f'Running BOSS via Docker: {bossdir}')
   return f'docker run --rm -v {abs_workdir}:/workspace -w /workspace -e BOSSdir={internal_bossdir} {bossdir} csh run_boss.csh'


def _generateWrapperScript(steps):
   """
   Write run_boss.csh that runs all BOSS steps sequentially.

   Parameters
   ----------
   steps : list of (par_filename, cmd_filename)
       Ordered list of PAR/CMD file pairs to execute.
   """

   lines = ['#!/bin/csh\n\n']

   for par, cmd in steps:
      lines.append(f'cp {par} parFile.par\n')
      lines.append(f'csh {cmd}\n')
      lines.append('if ($status != 0) exit $status\n\n')

   with open('run_boss.csh', 'w') as f:
      f.writelines(lines)


def run(zmatName, cgen, opt, charge, molname, workdir, debug, checkrun = True):
   """
   Run BOSS different times to generate Bonds, Angles, Dihedrals, Charges and VdW OPLSAA parameters 

   Parameters
   ----------
   zmatName : str
       Name of the Zmat file of the molecule
   cgen : str
       Charge method selected
   opt : int
       Number of optimizations
   charge : int
       Formal charge of the molecule
   molname : str
       Molecule name
   workdir : str
       Working directory
   debug : bool
       If True, temporal files are not removed

   Returns
   -------
   str, str
       outFile, pdbFile are the file names of the generated files
   """
       
   logger.info('Running BOSS')

   command = _getBossCommand(workdir, checkrun)

   with utilities.changedir(workdir):

      # Pre-generate all PAR and CMD files, then run BOSS once

      steps = []

      generatePARFile(cgen, charge, 'NEWZM', True,  'parFile_1.par')
      generateCMDFile('211', 'cout', 'bosscmd_1')
      steps.append(('parFile_1.par', 'bosscmd_1'))

      generatePARFile(cgen, charge, 'FULLM', False, 'parFile_2.par')
      generateCMDFile('711', 'out',  'bosscmd_2')
      steps.append(('parFile_2.par', 'bosscmd_2'))

      generatePARFile(cgen, charge, 'NEWZM', True,  'parFile_3.par')
      generateCMDFile('211', 'out',  'bosscmd_3')
      steps.append(('parFile_3.par', 'bosscmd_3'))

      for i in range(opt):
         n = 4 + i
         logger.info(f'Queuing BOSS optimization {i + 1}')
         generatePARFile(cgen, charge, 'NEWZM', False, f'parFile_{n}.par')
         generateCMDFile('211', 'out', f'bosscmd_{n}')
         steps.append((f'parFile_{n}.par', f'bosscmd_{n}'))

      shutil.copyfile(zmatName, 'optzmat')

      _generateWrapperScript(steps)

      result = subprocess.run(command, shell=True, capture_output=True, text=True, check=checkrun)

      shutil.copyfile('optzmat', zmatName)

      pdbFile, outFile = getOutputFilesNames(molname, workdir)

      if not os.path.isfile('plt.pdb'):
         logger.error('BOSS did not produce plt.pdb — the BOSS run likely failed.')
         if result.stderr:
            logger.error('BOSS stderr: %s', result.stderr.strip())
         exit()

      shutil.copyfile('plt.pdb', pdbFile)

   if not debug:
      n_steps = 3 + opt
      static_files = ['optzmat', 'parFile.par', 'cout', 'plt.pdb', 'sum', 'run_boss.csh']
      numbered_files = [f'parFile_{i+1}.par' for i in range(n_steps)] + \
                       [f'bosscmd_{i+1}' for i in range(n_steps)]
      for bossFile in static_files + numbered_files:
         path = os.path.join(workdir, bossFile)
         if os.path.exists(path):
            os.remove(path)

   return outFile, pdbFile

def getOutputFilesNames(molname, workdir):
   """
   Generate output BOSS file names (PDB, OUT file)

   Parameters
   ----------
   molname : str
      Molecule name
   workdir : str
      Working folder

   Returns
   -------
   pdbFile : str
      PDB file name
   outFile : str
      OUT file name
   """
       
   pdbFile = os.path.join(workdir, molname+'.pdb')
   outFile = os.path.join(workdir,'out')
       
   return pdbFile, outFile



scriptPAR = '''parg49: Gas-phase optimization
 The principal solvent is
NONE 
 QM method, charge calc & scale, solute charges:
aaaa
 The solute format is
ZMAT 
 Origin of the initial solvent coordinates is
NONE 
 Cap atom, radius and force constant:
   0    0.0000    0.0000
 Optimizer, ftol, simulated annealing parameters:
BFGS    0.000100bbbbb         0       0    0.0000    0.0000
 Conformational search parameters:
0           0.0000    0.0000    0.0000    0.0000    0.0000    0.0000
 Parameters for normal mode calculation:
  0  0  0    0.0000    0.0000
 NMOL, IBOX and BOXCUT for principal solvent:
   0   0  0.00
 Second solvent and number of molecules:
NONE    0
 Center atoms of solute1 & 2 and custom solvent, and ICUTAS array:
  0  0  0  0  0  0  0  0
 Atoms solute1 & 2 are rotated about:
  0  0
 Cutoff method (ICUT) and ICUTAT array:
  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
 IRECNT, INDSOL, IZLONG, MAXOVL, NOXX, NOSS, NOBNDV, NOANGV, NONEBN:
  0  1  0  0  0  0  0  0  0
 No. of solvent-solvent and solute-solvent rdfs:
  0  0
 First atoms for solvent-solvent rdfs:
  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
 Second atoms for solvent-solvent rdfs:
  0  0  0  0  0  0  0  0  0  0  0  0  0  0  0
 First atoms for solute-solvent rdfs:
  0  0  0  0  0  0  0  0  0  0  0  0
 Second atoms for solute-solvent rdfs:
  0  0  0  0  0  0  0  0  0  0  0  0
 Minimum and increment for rdfs:
    0.0000    0.0000
 Min & inc for solvent-solvent pair dist.:
    0.0000    0.0000
 Min & inc for solvent-solvent energy dist.:
    0.0000    0.0000
 Min & inc for solute-solvent pair dist.:
    0.0000    0.0000
 Min & inc for solute-solvent energy dist.:
    0.0000    0.0000
 Frequency of volume & solute moves, and MAXVAR:
     0     0     0
 Freq. of coord output, NBUSE, NOCUT, NOSMTH:
     0     0     0     0
 Range for volume moves, and WKC:
    0.0000    0.0000
 Ranges for solvent translations & rotations, & radius for SASA:
    0.0000    0.0000    0.0000
 Ranges for solute1 translations and rotations:
    0.0000    0.0000
 Ranges for solute2 translations and rotations:
    0.0000    0.0000
 For local heating, solute number and temperature:
   0    0.0000
 Solvent-solvent, solute-solvent, NB cutoffs:
    0.0000    0.0000  100.0000
 Temperature, pressure, & torsion cutoff:
    0.0000    0.0000    0.0000
 Diel. constant, 1-4 Coulomb & LJ scale factors, e(Rxn Field):
    1.0000    2.0000    2.0000    1.0000
 Format for plt files, & solute for E components:
PDB     1
'''

scriptCMD = '''#***********************************************************************
echo '     QM BOSS Calculation'
#***********************************************************************
nice +19
set boss           = $BOSSdir/BOSS
set configurations = "cccc"
set lambda         = "0.000 0.000 0.000"
set boxes          = $BOSSdir

setenv INFILE    optin
setenv UPFILE    optup
setenv SAVE      svopt
setenv AVERAGE   optav
setenv ZMATRIX   optzmat
setenv SLVZMAT   slvzmat
setenv BANGPAR   $BOSSdir/oplsaa.sb
setenv WATERBOX  $boxes/watbox
setenv ORG1BOX   $boxes/org1box
setenv ORG2BOX   $boxes/org2box
setenv SUMMARY   sum
setenv OUTPUT    aaaa
setenv PLTFILE   plt.pdb

if (-e tmppar) rm tmppar
cp parFile.par tmppar
cat $BOSSdir/oplsaa.par >> tmppar
setenv PARAMETER tmppar

date
time $boss bbbb $configurations $lambda
rm slvzmat svopt optav optup optin tmppar
cp sum optzmat
exit

'''


scriptCMDFEP = '''#***********************************************************************
echo '                 MC/gas simulation'
echo '                    gas phase 25 C '
echo '                 Equilibration  0.2M '
echo '                   Averaging  0-1M '
#***********************************************************************
#
nice +19
set boss = $BOSSdir/BOSS
set boxes = $BOSSdir

@ i = 0

while ($i < aaaa)

bbbb

        set lambda = "$rc0 $rc1 $rc2"

        setenv INFILE    g${lab}in
        setenv UPFILE    g${lab}up
        setenv SAVE      g${lab}sv
        setenv AVERAGE   g${lab}av
        setenv ZMATRIX   gaszmat
        setenv SLVZMAT   slvzmt

        # The gaspar0 file is only used for this initial window; gaspar
        # is used for subsequent windows. The difference is that the
        # subsequent windows use ZIN and IN for the initial solute and
        # solvent coordinates, while here they come from ZMAT and BOXES.
        if (-e tmpgas) rm tmpgas
        if ($i == 0) then
                cp gaspar0 tmpgas
        else
                cp gaspar tmpgas
        endif
        cat $BOSSdir/oplsaa.par >> tmpgas
        setenv PARAMETER tmpgas

        setenv BANGPAR   $boxes/oplsaa.sb
        setenv WATERBOX  $boxes/watbox
        setenv ORG1BOX   $boxes/org1box
        setenv ORG2BOX   $boxes/org2box
        setenv SUMMARY   g${lab}sum

        date

        setenv OUTPUT    g${lab}ota
        setenv PLTFILE   g${lab}plta

        #    Equilibration

        set configurations = "100000"
        echo time $boss 111 $configurations $lambda
        time $boss 111 $configurations $lambda
        foreach block (eq)
                date
                setenv OUTPUT    g${lab}ot$block
                setenv PLTFILE   g${lab}plt$block
                echo time $boss 001 $configurations $lambda
                time $boss 001 $configurations $lambda
        end

        #    Averaging

        set configurations = "250000"
        setenv OUTPUT    g${lab}otb
        setenv PLTFILE   g${lab}pltb
        rm g${lab}sv

        echo time $boss 011 $configurations $lambda
        time $boss 011 $configurations $lambda
        foreach block (c d e1)
                date
                setenv OUTPUT    g${lab}ot$block
                setenv PLTFILE   g${lab}plt$block
                echo time $boss 001 $configurations $lambda
                time $boss 001 $configurations $lambda
        end

        rm $SLVZMAT
        rm tmpgas

        if ($i < (aaaa - 1)) cp g${lab}in g${nex}in

        @ i++
end

date
exit


'''
