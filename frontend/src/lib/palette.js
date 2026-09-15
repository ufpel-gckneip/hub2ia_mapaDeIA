// Categorical palette for topics (RGB triples for deck.gl).
export const PALETTE = [
	[230, 25, 75], [60, 180, 75], [255, 225, 25], [67, 99, 216], [245, 130, 49],
	[145, 30, 180], [66, 212, 244], [240, 50, 230], [191, 239, 69], [250, 190, 190],
	[70, 153, 144], [220, 190, 255], [154, 99, 36], [128, 0, 0], [170, 255, 195],
	[128, 128, 0], [255, 216, 177], [0, 0, 117], [169, 169, 169], [230, 190, 255]
];

export function topicColor(topicId) {
	if (topicId == null || topicId < 0) return [136, 136, 136];
	return PALETTE[topicId % PALETTE.length];
}

export function rgbCss([r, g, b]) {
	return `rgb(${r},${g},${b})`;
}

// Approximate UF centroids (capital coords) for inter-state arcs.
export const STATE_CENTROIDS = {
	AC: [-67.8, -9.97], AL: [-35.7, -9.65], AP: [-51.05, 0.03], AM: [-60.0, -3.1],
	BA: [-38.5, -12.97], CE: [-38.5, -3.73], DF: [-47.9, -15.78], ES: [-40.3, -20.3],
	GO: [-49.3, -16.6], MA: [-44.3, -2.53], MT: [-56.1, -15.6], MS: [-54.6, -20.5],
	MG: [-43.9, -19.9], PA: [-48.5, -1.46], PB: [-34.8, -7.1], PR: [-49.3, -25.4],
	PE: [-34.9, -8.05], PI: [-42.8, -5.09], RJ: [-43.2, -22.9], RN: [-35.2, -5.79],
	RS: [-51.2, -30.03], RO: [-63.9, -8.76], RR: [-60.67, 2.82], SC: [-48.5, -27.6],
	SP: [-46.63, -23.55], SE: [-37.07, -10.9], TO: [-48.33, -10.18]
};
