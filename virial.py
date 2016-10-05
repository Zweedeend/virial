#!/usr/bin/env python
# -*- encoding: utf-8 -*-

"""
@date   November 2015, Malmö
@author M. Lund
"""

import os
from math import pi
from sys import exit

import numpy as np
from scipy.constants import N_A
from scipy.optimize import curve_fit


class RadialDistributionFunction:
  def __init__(self, filename):
    if os.path.isfile( filename ):
      d = np.loadtxt(filename)
      if d.shape[1]==2:
        self.r=d[:,0]
        self.g=d[:,1]
        self.w = -np.log(self.g)
        return
    exit( "Error loading g(r) from "+filename+" -- file does not exist or wrong format." )

  def slice(self, rmin, rmax):
    m = (self.r>=rmin) & (self.r<=rmax)
    return self.r[m], self.g[m]

  def normalizeVolume(self,dim):
    self.g = self.g / self.r**(dim-1)
    self.w = -np.log(self.g)

def VirialCoefficient(r, w, mw):
  b2={}
  b2['hs'] = 2*pi/3*min(r)**3          # zero -> contact assuming hard spheres
  b2['tot'] = b2['hs'] + np.trapz( -2*pi*(np.exp(-w)-1)*r**2, r)
  b2['reduced'] = b2['tot'] / b2['hs']
  b2['hsrange'] = [0,min(r)]
  b2['range'] = [0,max(r)]
  if mw[0]>0 and mw[1]>0:
    b2['mlmol/g2'] = b2['tot']*N_A*1e-24/mw[0]/mw[1]
  return b2

# If run as main program

if __name__ == "__main__":
  import argparse

  ps = argparse.ArgumentParser(
      prog = 'virial.py',
      description = 'Fit tail of RDFs to model pair potentials',
      formatter_class=argparse.ArgumentDefaultsHelpFormatter )
  ps.add_argument('-nm', action='store_true', help='assume distance in infile is in nanometers')
  ps.add_argument('-z', type=float, nargs=2, default=[0,0], metavar=('z1','z2'), help='valencies')
  ps.add_argument('-a','--radii', type=float, nargs=2, default=[0,0], metavar=('a1','a2'), help='radii [angstrom]')
  ps.add_argument('-mw', type=float, nargs=2, default=[0,0], metavar=('mw1','mw2'), help='mol. weights [g/mol]')
  ps.add_argument('-lB','--bjerrum', type=float, default=7.1, metavar=('lB'), help='Bjerrum length [angstrom]')
  ps.add_argument('-p', '--plot', action='store_true', help='plot fitted w(r) using matplotlib' )
  ps.add_argument('-so','--shiftonly', action='store_true',
      help='do not replace tail w. model potential' )
  ps.add_argument('--norm', choices=['no','2d', '3d'], default='no',
      help='normalize w. volume element')
  ps.add_argument('-r', '--range', type=float, nargs=2, metavar=('min','max'), required=True,
      help='fitting range [angstrom]')
  ps.add_argument('--pot', type=str,default='dh',help='pair-potential -- either from list or user-defined')
  ps.add_argument('--guess', type=float, nargs='+', help='initial guess for fitting parameters')
  ps.add_argument('--show', action='store_true', help='show list of built-in potentials and quit')
  ps.add_argument('-v','--version', action='version', version='%(prog)s 0.1')
  ps.add_argument('infile', type=str, help='two column input file with radial distribution function, g(r)' )
  ps.add_argument('outfile', type=str, help='three column output with manipulated r, w(r), g(r)' )
  args = ps.parse_args()

  # more convenient variable names
  lB = args.bjerrum
  a1,a2 = args.radii
  z1,z2 = args.z
  mw1,mw2 = args.mw

  # predefined potentials [ w(r)/kT, [guess parameters] ]
  potentiallist = {
      'dh'     : [ 'lB * z1 * z2 / r * np.exp( -r/a[0] ) + a[1]',  [30., 0] ],
      'dhsinh' : [ 'lB * z1 * z2 * sinh(a[1]/a[0])**2 / r * np.exp(-r/a[0]) + a[2]',  [30., 10.0, 0] ],
      'zero'   : [ 'r*0 + a[0]', [0] ]
      }

  if args.show==True:
    print 'pre-defined pair-potentials:\n'
    for key, val in potentiallist.iteritems():
      print "%10s = %s" % (key,val[0])
    print '\n(note: the last value of `a` is *always* used to shift data)\n'
    exit(0)

  if args.pot in potentiallist.keys():
    args.guess = potentiallist[args.pot][1]
    args.pot   = potentiallist[args.pot][0]

  exec 'def pot(r,*a): return '+args.pot # create pairpot function

  # load g(r) from disk
  if os.path.isfile( args.infile ):
    rdf = RadialDistributionFunction( args.infile )
  else:
    exit( "Error: File "+args.infile+" does not exist." )

  # convert to angstrom; normalize volume
  if args.nm == True: rdf.r = 10*rdf.r
  if args.norm=='2d': rdf.normalizeVolume(2)
  if args.norm=='3d': rdf.normalizeVolume(3)

  # cut out range and fit
  r, g = rdf.slice( *args.range )
  a = curve_fit( pot, r, -np.log(g), args.guess )[0]
  print 'model potential:'
  print '   w(r)/kT =', args.pot
  print '         a =', a, '(fitted)'
  print '        Mw =', args.mw, 'g/mol'
  print '     radii =', args.radii, 'AA'
  print '   charges =', args.z
  print ' fit range =', args.range, 'AA'

  # merge fitted data and model tail if needed
  if args.shiftonly == True:
    r, w = rdf.r, rdf.w - a[-1]
  else:
    dr = rdf.r[1]-rdf.r[0]           # data point separation in r
    rdf.w = rdf.w - a[-1]            # shift loaded data...
    a[-1] = 0                        # ...and set shift to zero
    shead = ( rdf.r<=args.range[0] ) # slice for data points < rmin
    rtail = np.arange( args.range[0], 4*args.range[1], dr ) # model pot > rmin
    r = np.concatenate( [ rdf.r[shead], rtail ] )
    w = np.concatenate( [ rdf.w[shead], pot(rtail,*a) ] )
    
  # virial coefficient
  B2 = VirialCoefficient( r, w, args.mw )
  print '\nvirial coefficient:'
  print '  B2hs    =', B2['hs'], 'A3 (', B2['hsrange'], ')'
  print '  B2      =', B2['tot'], 'A3 =', B2.get('mlmol/g2', 'NaN'), 'ml*mol/g2', ' (', B2['range'], ')'
  print '  B2/B2hs =', B2['reduced']

  # plot final w(r)
  if args.plot == True:
    import matplotlib.pyplot as plt
    plt.xlabel('$r$', fontsize=24)
    plt.ylabel('$\\beta w(r) = -\\ln g(r)$', fontsize=24)
    plt.plot( rdf.r, rdf.w, 'r.' )
    plt.plot( r, w, 'k-' )
    plt.show()

  # save final pmf to disk
  if args.outfile:
    np.savetxt(args.outfile, np.transpose( (r, w, np.exp(-w)) ) )
