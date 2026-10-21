/** @type {import('@brookesia/shared-utils').BrookesiaConfig} */
module.exports = {
  cli: {
    sourceRoot: 'src',
    outputPath: 'build',
    releasePath: 'dist',
    signRoot: 'sign',
  },
  // Retain compressed PNG assets to save the board's limited Flash filesystem.
  convertImages: false,
};
